"""
System Status Manager - Kill Switch Implementation

Manages system-wide operational status with Redis caching and DB persistence.
Provides fast checks for whether the system is operational or in maintenance mode.
"""

import redis
import logging
import json
from typing import Optional, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel
from sqlalchemy import text

from src.config.settings import settings
from src.shared.database.connection import db_manager

logger = logging.getLogger(__name__)

# Redis keys
SYSTEM_STATUS_KEY = "system:status"
SYSTEM_STATUS_TTL = 300  # 5 minutes cache

SystemStatusType = Literal["active", "maintenance", "degraded"]


class SystemStatus(BaseModel):
    """System status model"""
    status: SystemStatusType
    enabled: bool
    reason: Optional[str] = None
    initiated_by: Optional[str] = None
    initiated_at: datetime
    maintenance_message: Optional[str] = None
    expected_restoration: Optional[datetime] = None
    metadata: Dict[str, Any] = {}


class SystemStatusManager:
    """
    Manage system operational status

    Provides three-tier caching for ultra-fast status checks:
    1. In-memory cache (fastest, ns latency)
    2. Redis cache (fast, sub-ms latency)
    3. PostgreSQL (source of truth)
    """

    def __init__(self):
        self.redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        self._cache: Optional[SystemStatus] = None

    def get_status(self) -> SystemStatus:
        """
        Get current system status with multi-layer caching

        Priority:
        1. In-memory cache (fastest)
        2. Redis cache (fast)
        3. Database (source of truth)

        Returns:
            SystemStatus with current operational state
        """
        # Layer 1: In-memory cache
        if self._cache:
            return self._cache

        # Layer 2: Redis cache
        try:
            cached = self.redis_client.get(SYSTEM_STATUS_KEY)
            if cached:
                status_data = json.loads(cached)
                # Parse datetime strings
                status_data['initiated_at'] = datetime.fromisoformat(status_data['initiated_at'])
                if status_data.get('expected_restoration'):
                    status_data['expected_restoration'] = datetime.fromisoformat(status_data['expected_restoration'])

                status = SystemStatus(**status_data)
                self._cache = status
                return status
        except Exception as e:
            logger.warning(f"Redis cache miss: {e}")

        # Layer 3: Database
        status = self._get_from_db()
        self._update_cache(status)
        return status

    def set_maintenance_mode(
        self,
        enabled: bool,
        reason: str,
        initiated_by: str,
        message: Optional[str] = None,
        expected_restoration: Optional[datetime] = None
    ) -> SystemStatus:
        """
        Enable or disable maintenance mode (kill switch)

        Args:
            enabled: True to enable maintenance, False to disable
            reason: Reason for status change
            initiated_by: User/system initiating change
            message: Public message to display to users
            expected_restoration: Expected time when service will be restored

        Returns:
            Updated system status
        """
        status_value: SystemStatusType = "maintenance" if enabled else "active"

        with db_manager.get_session() as session:
            # Update system_status table
            session.execute(
                text("""
                    UPDATE system_status
                    SET status = :status,
                        enabled = :enabled,
                        reason = :reason,
                        initiated_by = :initiated_by,
                        initiated_at = NOW(),
                        maintenance_message = :message,
                        expected_restoration = :restoration
                    WHERE id = (SELECT id FROM system_status LIMIT 1)
                """),
                {
                    "status": status_value,
                    "enabled": not enabled,  # enabled=False when in maintenance
                    "reason": reason,
                    "initiated_by": initiated_by,
                    "message": message,
                    "restoration": expected_restoration
                }
            )

            # Create audit record
            session.execute(
                text("""
                    INSERT INTO system_status_audit
                    (status, enabled, reason, initiated_by, maintenance_message, expected_restoration, metadata)
                    VALUES (:status, :enabled, :reason, :initiated_by, :message, :restoration, :metadata)
                """),
                {
                    "status": status_value,
                    "enabled": not enabled,
                    "reason": reason,
                    "initiated_by": initiated_by,
                    "message": message,
                    "restoration": expected_restoration,
                    "metadata": json.dumps({
                        "timestamp": datetime.utcnow().isoformat()
                    })
                }
            )

            session.commit()

        # Refresh cache
        status = self._get_from_db()
        self._update_cache(status)

        logger.info(
            f"System status changed to {status_value} by {initiated_by}: {reason}"
        )

        return status

    def check_system_operational(self) -> bool:
        """
        Fast check if system is operational

        This is the primary method called by middleware on every request.
        Uses multi-layer caching for sub-millisecond response time.

        Returns:
            True if system is accepting requests, False if in maintenance
        """
        status = self.get_status()
        return status.enabled and status.status == "active"

    def _get_from_db(self) -> SystemStatus:
        """Get status from database (source of truth)"""
        try:
            with db_manager.get_session() as session:
                result = session.execute(
                    text("SELECT * FROM system_status LIMIT 1")
                ).fetchone()

                if not result:
                    # Fallback: create default active status
                    logger.warning("No system status found in DB, creating default")
                    session.execute(
                        text("""
                            INSERT INTO system_status (status, enabled, reason, initiated_by)
                            VALUES ('active', TRUE, 'System initialized', 'system')
                        """)
                    )
                    session.commit()

                    return SystemStatus(
                        status="active",
                        enabled=True,
                        initiated_at=datetime.utcnow(),
                        initiated_by="system"
                    )

                return SystemStatus(
                    status=result.status,
                    enabled=result.enabled,
                    reason=result.reason,
                    initiated_by=result.initiated_by,
                    initiated_at=result.initiated_at,
                    maintenance_message=result.maintenance_message,
                    expected_restoration=result.expected_restoration,
                    metadata=result.metadata or {}
                )
        except Exception as e:
            logger.error(f"Failed to get status from database: {e}")
            # Fallback to safe default (maintenance mode to be safe)
            return SystemStatus(
                status="maintenance",
                enabled=False,
                initiated_at=datetime.utcnow(),
                initiated_by="system",
                reason="Database error - fail-safe mode"
            )

    def _update_cache(self, status: SystemStatus):
        """Update all cache layers"""
        # Update in-memory cache
        self._cache = status

        # Update Redis cache
        try:
            # Convert to JSON-serializable dict
            status_dict = status.model_dump()
            status_dict['initiated_at'] = status_dict['initiated_at'].isoformat()
            if status_dict.get('expected_restoration'):
                status_dict['expected_restoration'] = status_dict['expected_restoration'].isoformat()

            self.redis_client.setex(
                SYSTEM_STATUS_KEY,
                SYSTEM_STATUS_TTL,
                json.dumps(status_dict)
            )
        except Exception as e:
            logger.error(f"Failed to update Redis cache: {e}")

    def clear_cache(self):
        """Clear all caches (force refresh from DB on next check)"""
        self._cache = None
        try:
            self.redis_client.delete(SYSTEM_STATUS_KEY)
        except Exception as e:
            logger.warning(f"Failed to clear Redis cache: {e}")

    def get_audit_history(self, limit: int = 50) -> list[Dict[str, Any]]:
        """
        Get audit history of status changes

        Args:
            limit: Maximum number of records to return

        Returns:
            List of audit records
        """
        try:
            with db_manager.get_session() as session:
                results = session.execute(
                    text("""
                        SELECT status, enabled, reason, initiated_by,
                               maintenance_message, expected_restoration, created_at
                        FROM system_status_audit
                        ORDER BY created_at DESC
                        LIMIT :limit
                    """),
                    {"limit": limit}
                ).fetchall()

                return [
                    {
                        "status": r.status,
                        "enabled": r.enabled,
                        "reason": r.reason,
                        "initiated_by": r.initiated_by,
                        "maintenance_message": r.maintenance_message,
                        "expected_restoration": r.expected_restoration.isoformat() if r.expected_restoration else None,
                        "created_at": r.created_at.isoformat()
                    }
                    for r in results
                ]
        except Exception as e:
            logger.error(f"Failed to get audit history: {e}")
            return []


# Global instance
system_status_manager = SystemStatusManager()
