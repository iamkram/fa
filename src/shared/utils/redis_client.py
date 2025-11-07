"""
Redis client for conversation session management

Stores and retrieves conversation history for FA sessions.
"""

import redis
import json
from typing import List, Dict, Any, Optional
from datetime import timedelta
import logging

from src.config.settings import settings

logger = logging.getLogger(__name__)


class RedisSessionManager:
    """Manage conversation sessions in Redis"""

    def __init__(self):
        self.client = redis.from_url(settings.redis_url, decode_responses=True)
        self.default_ttl = 86400  # 24 hours

    def _session_key(self, session_id: str) -> str:
        """Generate Redis key for session"""
        return f"session:{session_id}"

    def store_conversation_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        timestamp: str
    ):
        """Add a conversation turn to session history"""
        key = self._session_key(session_id)

        turn = {
            "role": role,
            "content": content,
            "timestamp": timestamp
        }

        # Append to list
        self.client.rpush(key, json.dumps(turn))

        # Set/refresh TTL
        self.client.expire(key, self.default_ttl)

    def get_conversation_history(
        self,
        session_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent conversation history"""
        key = self._session_key(session_id)

        # Get last N turns
        turns = self.client.lrange(key, -limit, -1)

        return [json.loads(turn) for turn in turns]

    def clear_session(self, session_id: str):
        """Clear session history"""
        key = self._session_key(session_id)
        self.client.delete(key)


# Global instance
redis_session_manager = RedisSessionManager()
