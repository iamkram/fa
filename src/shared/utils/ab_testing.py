"""
A/B Testing Framework

Manages A/B tests for prompt optimization and feature experimentation.
Uses consistent hashing for stable user assignment to test variants.
"""

import hashlib
import logging
import yaml
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class TestStatus(str, Enum):
    """A/B test status"""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    DRAFT = "draft"


@dataclass
class TestVariant:
    """A/B test variant configuration"""
    name: str
    description: str
    config: Dict[str, Any]
    allocation_pct: float


@dataclass
class ABTest:
    """A/B test definition"""
    test_id: str
    name: str
    description: str
    status: TestStatus
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    variants: List[TestVariant]
    metrics: List[str]
    control_variant: str


class ABTestManager:
    """Manage A/B tests and variant assignment"""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize A/B test manager

        Args:
            config_path: Path to ab_tests.yaml config file
        """
        if config_path is None:
            config_path = "config/ab_tests.yaml"

        self.config_path = Path(config_path)
        self.tests: Dict[str, ABTest] = {}
        self._load_tests()

    def _load_tests(self):
        """Load A/B tests from config file"""
        if not self.config_path.exists():
            logger.warning(f"A/B test config not found: {self.config_path}")
            self.tests = {}
            return

        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)

            if not config or 'tests' not in config:
                logger.warning("No tests found in config")
                self.tests = {}
                return

            # Parse tests
            for test_id, test_config in config['tests'].items():
                variants = [
                    TestVariant(
                        name=v['name'],
                        description=v.get('description', ''),
                        config=v.get('config', {}),
                        allocation_pct=v.get('allocation_pct', 50.0)
                    )
                    for v in test_config.get('variants', [])
                ]

                # Parse dates
                start_date = None
                end_date = None
                if 'start_date' in test_config:
                    start_date = datetime.fromisoformat(test_config['start_date'])
                if 'end_date' in test_config:
                    end_date = datetime.fromisoformat(test_config['end_date'])

                test = ABTest(
                    test_id=test_id,
                    name=test_config.get('name', test_id),
                    description=test_config.get('description', ''),
                    status=TestStatus(test_config.get('status', 'draft')),
                    start_date=start_date,
                    end_date=end_date,
                    variants=variants,
                    metrics=test_config.get('metrics', []),
                    control_variant=test_config.get('control_variant', 'control')
                )

                self.tests[test_id] = test

            logger.info(f"Loaded {len(self.tests)} A/B tests from config")

        except Exception as e:
            logger.error(f"Failed to load A/B test config: {e}")
            self.tests = {}

    def get_variant(
        self,
        test_id: str,
        user_id: str,
        force_variant: Optional[str] = None
    ) -> Optional[TestVariant]:
        """Get variant assignment for a user

        Uses consistent hashing to ensure the same user always gets the same variant.

        Args:
            test_id: Test identifier
            user_id: User identifier (e.g., FA ID, session ID)
            force_variant: Force a specific variant (for testing)

        Returns:
            TestVariant or None if test not found/inactive
        """
        # Check if test exists
        if test_id not in self.tests:
            logger.warning(f"Test {test_id} not found")
            return None

        test = self.tests[test_id]

        # Check if test is active
        if test.status != TestStatus.ACTIVE:
            logger.debug(f"Test {test_id} is not active (status: {test.status})")
            return None

        # Check date range
        now = datetime.utcnow()
        if test.start_date and now < test.start_date:
            logger.debug(f"Test {test_id} has not started yet")
            return None
        if test.end_date and now > test.end_date:
            logger.debug(f"Test {test_id} has ended")
            return None

        # Force variant if specified
        if force_variant:
            for variant in test.variants:
                if variant.name == force_variant:
                    logger.info(f"Forced variant {force_variant} for test {test_id}")
                    return variant

            logger.warning(f"Forced variant {force_variant} not found in test {test_id}")
            return None

        # Use consistent hashing for assignment
        variant = self._assign_variant_consistent(test, user_id)

        logger.debug(
            f"Assigned user {user_id} to variant '{variant.name}' "
            f"for test {test_id}"
        )

        return variant

    def _assign_variant_consistent(
        self,
        test: ABTest,
        user_id: str
    ) -> TestVariant:
        """Assign variant using consistent hashing

        Args:
            test: ABTest instance
            user_id: User identifier

        Returns:
            TestVariant
        """
        # Hash user ID with test ID for consistency
        hash_input = f"{test.test_id}:{user_id}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)

        # Normalize to 0-100
        hash_pct = (hash_value % 10000) / 100.0

        # Assign based on allocation percentages
        cumulative_pct = 0.0
        for variant in test.variants:
            cumulative_pct += variant.allocation_pct
            if hash_pct < cumulative_pct:
                return variant

        # Fallback to last variant (should not happen with proper allocations)
        return test.variants[-1]

    def get_config_for_user(
        self,
        user_id: str,
        test_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get merged configuration for all active tests

        Args:
            user_id: User identifier
            test_ids: Optional list of specific test IDs to check

        Returns:
            Merged configuration dict
        """
        config = {}

        # Check specified tests or all active tests
        tests_to_check = (
            [self.tests[tid] for tid in test_ids if tid in self.tests]
            if test_ids
            else self.tests.values()
        )

        for test in tests_to_check:
            if test.status == TestStatus.ACTIVE:
                variant = self.get_variant(test.test_id, user_id)
                if variant:
                    # Merge variant config
                    config.update(variant.config)

        return config

    def log_exposure(
        self,
        test_id: str,
        user_id: str,
        variant_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log that a user was exposed to a test variant

        Args:
            test_id: Test identifier
            user_id: User identifier
            variant_name: Variant name
            metadata: Optional metadata about the exposure
        """
        # In production, this would log to LangSmith or analytics platform
        logger.info(
            f"A/B Exposure: test={test_id}, user={user_id}, "
            f"variant={variant_name}, metadata={metadata}"
        )

    def log_metric(
        self,
        test_id: str,
        user_id: str,
        variant_name: str,
        metric_name: str,
        metric_value: float,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log a metric for A/B test analysis

        Args:
            test_id: Test identifier
            user_id: User identifier
            variant_name: Variant name
            metric_name: Metric name (e.g., "response_time_ms", "thumbs_up")
            metric_value: Metric value
            metadata: Optional metadata
        """
        # In production, this would log to LangSmith or analytics platform
        logger.info(
            f"A/B Metric: test={test_id}, user={user_id}, "
            f"variant={variant_name}, metric={metric_name}, "
            f"value={metric_value}, metadata={metadata}"
        )

    def get_active_tests(self) -> List[ABTest]:
        """Get all active tests

        Returns:
            List of active ABTest instances
        """
        now = datetime.utcnow()

        active_tests = []
        for test in self.tests.values():
            if test.status != TestStatus.ACTIVE:
                continue

            # Check date range
            if test.start_date and now < test.start_date:
                continue
            if test.end_date and now > test.end_date:
                continue

            active_tests.append(test)

        return active_tests

    def get_test_summary(self, test_id: str) -> Optional[Dict[str, Any]]:
        """Get summary information about a test

        Args:
            test_id: Test identifier

        Returns:
            Summary dict or None
        """
        if test_id not in self.tests:
            return None

        test = self.tests[test_id]

        return {
            "test_id": test.test_id,
            "name": test.name,
            "description": test.description,
            "status": test.status.value,
            "start_date": test.start_date.isoformat() if test.start_date else None,
            "end_date": test.end_date.isoformat() if test.end_date else None,
            "variants": [
                {
                    "name": v.name,
                    "description": v.description,
                    "allocation_pct": v.allocation_pct
                }
                for v in test.variants
            ],
            "metrics": test.metrics,
            "control_variant": test.control_variant
        }


# Global instance
ab_test_manager = ABTestManager()
