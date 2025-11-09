"""Validation Agent - Pre-deployment testing of improvement proposals"""

from langchain_anthropic import ChatAnthropic
from langsmith import Client
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
import logging
import json
import uuid
import asyncio

from src.config.settings import settings
from src.shared.database.connection import get_db
from src.shared.models.meta_monitoring import (
    ImprovementProposal,
    ValidationResult,
    MetaEvaluationRun
)

logger = logging.getLogger(__name__)


class ValidationAgent:
    """Agent for pre-deployment validation of improvement proposals"""

    def __init__(self):
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            temperature=0.0,
            max_tokens=4000,
            anthropic_api_key=settings.anthropic_api_key
        )
        # LangSmith client for test execution
        self.langsmith_client = Client(api_key=settings.langsmith_api_key)
        self.main_project = "fa-ai-dev"
        self.meta_project = "fa-ai-meta-monitoring"

        # Golden test dataset size
        self.test_dataset_size = 100

    async def validate_proposal(
        self,
        proposal_id: str,
        run_tests: bool = True
    ) -> Dict[str, Any]:
        """Validate an improvement proposal through testing

        Args:
            proposal_id: ID of proposal to validate
            run_tests: Whether to actually run tests (False for dry-run)

        Returns:
            Validation results
        """
        logger.info(f"[ValidationAgent] Validating proposal {proposal_id}")

        db = next(get_db())
        validation_id = uuid.uuid4()

        try:
            # 1. Get proposal
            proposal = db.query(ImprovementProposal).filter(
                ImprovementProposal.proposal_id == proposal_id
            ).first()

            if not proposal:
                raise ValueError(f"Proposal {proposal_id} not found")

            # 2. Get baseline metrics
            baseline_metrics = await self._get_baseline_metrics(db)

            # 3. Create validation record
            validation = ValidationResult(
                validation_id=validation_id,
                proposal_id=uuid.UUID(proposal_id),
                started_at=datetime.utcnow(),
                status='running',
                baseline_metrics=baseline_metrics
            )
            db.add(validation)
            db.commit()

            if not run_tests:
                logger.info(f"[ValidationAgent] Dry-run mode - skipping actual tests")
                validation.status = 'skipped'
                validation.completed_at = datetime.utcnow()
                db.commit()
                return {"status": "skipped", "validation_id": str(validation_id)}

            # 4. Prepare test environment
            test_setup = await self._prepare_test_environment(proposal, db)

            # 5. Run validation tests
            test_results = await self._run_validation_tests(proposal, test_setup)

            # 6. Calculate metrics
            test_metrics = self._calculate_test_metrics(test_results)

            # 7. Compare against baseline
            improvement_delta = self._calculate_improvement_delta(
                baseline_metrics, test_metrics
            )

            # 8. Detect regressions
            regressions_detected, regression_details = self._detect_regressions(
                baseline_metrics, test_metrics
            )

            # 9. Update validation record
            validation.completed_at = datetime.utcnow()
            validation.status = 'failed' if regressions_detected else 'passed'
            validation.test_dataset_size = len(test_results)
            validation.tests_passed = sum(1 for t in test_results if t.get('passed', False))
            validation.tests_failed = len(test_results) - validation.tests_passed
            validation.test_metrics = test_metrics
            validation.improvement_delta = improvement_delta
            validation.regressions_detected = regressions_detected
            validation.regression_details = regression_details
            validation.test_output = json.dumps(test_results[:10], indent=2)  # Sample output

            db.commit()

            logger.info(
                f"[ValidationAgent] Validation complete for {proposal_id}: "
                f"{'PASSED' if not regressions_detected else 'FAILED'} "
                f"({validation.tests_passed}/{len(test_results)} tests passed)"
            )

            return {
                "validation_id": str(validation_id),
                "status": validation.status,
                "tests_passed": validation.tests_passed,
                "tests_failed": validation.tests_failed,
                "regressions_detected": regressions_detected,
                "improvement_delta": improvement_delta
            }

        except Exception as e:
            logger.error(f"[ValidationAgent] Error validating proposal {proposal_id}: {e}", exc_info=True)

            # Mark validation as failed
            try:
                validation = db.query(ValidationResult).filter(
                    ValidationResult.validation_id == validation_id
                ).first()
                if validation:
                    validation.status = 'failed'
                    validation.completed_at = datetime.utcnow()
                    validation.error_logs = str(e)
                    db.commit()
            except:
                pass

            return {"status": "failed", "error": str(e)}
        finally:
            db.close()

    async def _get_baseline_metrics(self, db: Session) -> Dict[str, Any]:
        """Get baseline metrics from most recent evaluation"""
        baseline_run = db.query(MetaEvaluationRun).filter(
            MetaEvaluationRun.run_type == 'baseline',
            MetaEvaluationRun.status == 'completed'
        ).first()

        if baseline_run:
            return {
                "fact_accuracy": baseline_run.fact_accuracy_score,
                "guardrail_pass_rate": baseline_run.guardrail_pass_rate,
                "avg_response_time_ms": baseline_run.avg_response_time_ms,
                "sla_compliance_rate": baseline_run.sla_compliance_rate,
                "error_rate": 0.02  # Default baseline
            }
        else:
            # Use hardcoded baseline
            return {
                "fact_accuracy": 0.93,
                "guardrail_pass_rate": 0.98,
                "avg_response_time_ms": 2000,
                "sla_compliance_rate": 0.95,
                "error_rate": 0.02
            }

    async def _prepare_test_environment(
        self,
        proposal: ImprovementProposal,
        db: Session
    ) -> Dict[str, Any]:
        """Prepare isolated test environment for validation

        NOTE: In full implementation, this would:
        1. Create a copy of the system in a sandbox
        2. Apply the proposed changes
        3. Set up monitoring

        For now, we'll simulate this process.
        """
        logger.info(f"[ValidationAgent] Preparing test environment for {proposal.proposal_type}")

        return {
            "environment": "sandbox",
            "proposal_applied": True,
            "changes_applied": proposal.proposed_changes,
            "ready": True
        }

    async def _run_validation_tests(
        self,
        proposal: ImprovementProposal,
        test_setup: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Run validation tests on golden dataset

        NOTE: In full implementation, this would:
        1. Load golden test dataset from LangSmith
        2. Run each test case through the modified system
        3. Compare outputs

        For now, we'll simulate test execution.
        """
        logger.info(f"[ValidationAgent] Running {self.test_dataset_size} validation tests")

        # Simulate running tests
        # In production, this would actually execute the test suite
        test_results = []

        for i in range(min(self.test_dataset_size, 20)):  # Simulate 20 tests for now
            # Simulated test result
            passed = True  # Most tests should pass for valid proposals
            if i % 10 == 0:  # 10% failure rate simulation
                passed = False

            test_results.append({
                "test_id": f"test_{i+1}",
                "passed": passed,
                "fact_accuracy": 0.95 if passed else 0.85,
                "guardrail_passed": passed,
                "response_time_ms": 1800 + (i * 10),
                "error": None if passed else "Simulated test failure"
            })

        return test_results

    def _calculate_test_metrics(self, test_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate aggregate metrics from test results"""
        if not test_results:
            return {}

        from statistics import mean

        return {
            "fact_accuracy": mean([t.get('fact_accuracy', 0) for t in test_results if t.get('fact_accuracy')]),
            "guardrail_pass_rate": sum(1 for t in test_results if t.get('guardrail_passed', False)) / len(test_results),
            "avg_response_time_ms": int(mean([t.get('response_time_ms', 0) for t in test_results if t.get('response_time_ms')])),
            "sla_compliance_rate": sum(1 for t in test_results if t.get('response_time_ms', 0) < 3000) / len(test_results),
            "error_rate": sum(1 for t in test_results if not t.get('passed', False)) / len(test_results)
        }

    def _calculate_improvement_delta(
        self,
        baseline: Dict[str, Any],
        test: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate percentage improvement from baseline to test"""
        delta = {}

        for metric in ['fact_accuracy', 'guardrail_pass_rate', 'sla_compliance_rate']:
            if metric in baseline and metric in test:
                baseline_val = baseline[metric]
                test_val = test[metric]
                if baseline_val > 0:
                    delta[metric] = {
                        "baseline": baseline_val,
                        "test": test_val,
                        "delta_pct": ((test_val - baseline_val) / baseline_val) * 100,
                        "improved": test_val > baseline_val
                    }

        # For response time and error rate, lower is better
        for metric in ['avg_response_time_ms', 'error_rate']:
            if metric in baseline and metric in test:
                baseline_val = baseline[metric]
                test_val = test[metric]
                if baseline_val > 0:
                    delta[metric] = {
                        "baseline": baseline_val,
                        "test": test_val,
                        "delta_pct": ((baseline_val - test_val) / baseline_val) * 100,
                        "improved": test_val < baseline_val
                    }

        return delta

    def _detect_regressions(
        self,
        baseline: Dict[str, Any],
        test: Dict[str, Any],
        threshold_pct: float = 5.0
    ) -> tuple[bool, Optional[Dict[str, Any]]]:
        """Detect if proposed change causes regressions

        Args:
            baseline: Baseline metrics
            test: Test metrics
            threshold_pct: Percentage degradation threshold (default 5%)

        Returns:
            (has_regressions, regression_details)
        """
        regressions = []

        # Check for degradation in key metrics
        for metric in ['fact_accuracy', 'guardrail_pass_rate', 'sla_compliance_rate']:
            if metric in baseline and metric in test:
                baseline_val = baseline[metric]
                test_val = test[metric]

                degradation_pct = ((baseline_val - test_val) / baseline_val) * 100

                if degradation_pct > threshold_pct:
                    regressions.append({
                        "metric": metric,
                        "baseline": baseline_val,
                        "test": test_val,
                        "degradation_pct": round(degradation_pct, 2),
                        "threshold_pct": threshold_pct
                    })

        # Check for increase in error rate or response time
        for metric in ['avg_response_time_ms', 'error_rate']:
            if metric in baseline and metric in test:
                baseline_val = baseline[metric]
                test_val = test[metric]

                increase_pct = ((test_val - baseline_val) / baseline_val) * 100

                if increase_pct > threshold_pct:
                    regressions.append({
                        "metric": metric,
                        "baseline": baseline_val,
                        "test": test_val,
                        "increase_pct": round(increase_pct, 2),
                        "threshold_pct": threshold_pct
                    })

        if regressions:
            return True, {"regressions": regressions, "count": len(regressions)}
        else:
            return False, None


# Main entry point
async def run_validation_agent(proposal_id: str, run_tests: bool = True):
    """Run the validation agent

    Args:
        proposal_id: ID of proposal to validate
        run_tests: Whether to run actual tests
    """
    agent = ValidationAgent()
    return await agent.validate_proposal(proposal_id, run_tests=run_tests)


if __name__ == "__main__":
    # For testing
    import asyncio
    # Example: asyncio.run(run_validation_agent("some-proposal-id"))
    print("ValidationAgent ready. Call run_validation_agent(proposal_id) to validate a proposal.")
