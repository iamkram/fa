"""
Guardrail Metrics Tracking

Tracks guardrail events, performance, and effectiveness metrics for monitoring and optimization.
Integrates with LangSmith for feedback and Redis for aggregation.
"""

import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import json

from langsmith import Client
from src.config.settings import settings

logger = logging.getLogger(__name__)


class GuardrailMetricsTracker:
    """Track and aggregate guardrail metrics for monitoring"""

    def __init__(self):
        """Initialize metrics tracker"""
        self.langsmith_client = Client(api_key=settings.langsmith_api_key)
        self._session_metrics: Dict[str, Any] = defaultdict(lambda: {
            "input_guardrail_triggers": 0,
            "output_guardrail_triggers": 0,
            "fact_verification_flags": 0,
            "llm_validations_performed": 0,
            "total_processing_time_ms": 0,
            "queries_processed": 0,
            "confidence_scores": []
        })

    def track_input_guardrail(
        self,
        session_id: str,
        query_id: str,
        flags: List[Any],
        input_safe: bool,
        llm_performed: bool = False,
        processing_time_ms: int = 0
    ):
        """
        Track input guardrail event

        Args:
            session_id: Session identifier
            query_id: Query identifier
            flags: List of guardrail flags triggered
            input_safe: Whether input passed validation
            llm_performed: Whether LLM validation was performed
            processing_time_ms: Processing time in milliseconds
        """
        try:
            metrics = {
                "event_type": "input_guardrail",
                "session_id": session_id,
                "query_id": query_id,
                "timestamp": datetime.utcnow().isoformat(),
                "input_safe": input_safe,
                "flags_count": len(flags),
                "flags": [str(f) for f in flags],
                "llm_validation_performed": llm_performed,
                "processing_time_ms": processing_time_ms
            }

            # Update session aggregates
            if not input_safe:
                self._session_metrics[session_id]["input_guardrail_triggers"] += 1

            if llm_performed:
                self._session_metrics[session_id]["llm_validations_performed"] += 1

            self._session_metrics[session_id]["total_processing_time_ms"] += processing_time_ms

            # Log metrics
            logger.info(f"[Metrics] Input Guardrail: {json.dumps(metrics)}")

            # Send to LangSmith as metadata
            self._send_to_langsmith("input_guardrail", metrics)

        except Exception as e:
            logger.error(f"Failed to track input guardrail metrics: {e}")

    def track_output_guardrail(
        self,
        session_id: str,
        query_id: str,
        flags: List[Any],
        output_safe: bool,
        llm_performed: bool = False,
        processing_time_ms: int = 0,
        pii_count: int = 0,
        hallucination_count: int = 0,
        compliance_count: int = 0
    ):
        """
        Track output guardrail event

        Args:
            session_id: Session identifier
            query_id: Query identifier
            flags: List of guardrail flags triggered
            output_safe: Whether output passed validation
            llm_performed: Whether LLM validation was performed
            processing_time_ms: Processing time in milliseconds
            pii_count: Number of PII items detected
            hallucination_count: Number of hallucinations detected
            compliance_count: Number of compliance issues detected
        """
        try:
            metrics = {
                "event_type": "output_guardrail",
                "session_id": session_id,
                "query_id": query_id,
                "timestamp": datetime.utcnow().isoformat(),
                "output_safe": output_safe,
                "flags_count": len(flags),
                "flags": [str(f) for f in flags],
                "llm_validation_performed": llm_performed,
                "processing_time_ms": processing_time_ms,
                "breakdown": {
                    "pii_count": pii_count,
                    "hallucination_count": hallucination_count,
                    "compliance_count": compliance_count
                }
            }

            # Update session aggregates
            if not output_safe:
                self._session_metrics[session_id]["output_guardrail_triggers"] += 1

            if llm_performed:
                self._session_metrics[session_id]["llm_validations_performed"] += 1

            self._session_metrics[session_id]["total_processing_time_ms"] += processing_time_ms

            # Log metrics
            logger.info(f"[Metrics] Output Guardrail: {json.dumps(metrics)}")

            # Send to LangSmith
            self._send_to_langsmith("output_guardrail", metrics)

        except Exception as e:
            logger.error(f"Failed to track output guardrail metrics: {e}")

    def track_fact_verification(
        self,
        session_id: str,
        query_id: str,
        confidence_score: float,
        verification_passed: bool,
        llm_performed: bool,
        source_count: int,
        hallucination_details: Optional[List[Dict]] = None,
        processing_time_ms: int = 0
    ):
        """
        Track fact verification event

        Args:
            session_id: Session identifier
            query_id: Query identifier
            confidence_score: Verification confidence score (0.0-1.0)
            verification_passed: Whether verification passed
            llm_performed: Whether LLM validation was performed
            source_count: Number of sources used for verification
            hallucination_details: List of hallucination details if any
            processing_time_ms: Processing time in milliseconds
        """
        try:
            metrics = {
                "event_type": "fact_verification",
                "session_id": session_id,
                "query_id": query_id,
                "timestamp": datetime.utcnow().isoformat(),
                "confidence_score": confidence_score,
                "verification_passed": verification_passed,
                "llm_validation_performed": llm_performed,
                "source_count": source_count,
                "hallucination_count": len(hallucination_details) if hallucination_details else 0,
                "processing_time_ms": processing_time_ms
            }

            # Update session aggregates
            if not verification_passed:
                self._session_metrics[session_id]["fact_verification_flags"] += 1

            if llm_performed:
                self._session_metrics[session_id]["llm_validations_performed"] += 1

            self._session_metrics[session_id]["confidence_scores"].append(confidence_score)
            self._session_metrics[session_id]["total_processing_time_ms"] += processing_time_ms

            # Log metrics
            logger.info(f"[Metrics] Fact Verification: confidence={confidence_score:.3f}, sources={source_count}")

            # Send to LangSmith with detailed hallucination info
            if hallucination_details:
                metrics["hallucination_details"] = hallucination_details

            self._send_to_langsmith("fact_verification", metrics)

            # Send confidence score as feedback to LangSmith if we have a run_id
            # This will be done in the API layer where we have the run_id

        except Exception as e:
            logger.error(f"Failed to track fact verification metrics: {e}")

    def track_llm_validation_performance(
        self,
        validation_type: str,
        session_id: str,
        query_id: str,
        latency_ms: int,
        cache_hit: bool,
        success: bool,
        error: Optional[str] = None
    ):
        """
        Track LLM validation performance

        Args:
            validation_type: Type of validation (pii, injection, hallucination, etc.)
            session_id: Session identifier
            query_id: Query identifier
            latency_ms: Validation latency in milliseconds
            cache_hit: Whether result was from cache
            success: Whether validation succeeded
            error: Error message if failed
        """
        try:
            metrics = {
                "event_type": "llm_validation_performance",
                "validation_type": validation_type,
                "session_id": session_id,
                "query_id": query_id,
                "timestamp": datetime.utcnow().isoformat(),
                "latency_ms": latency_ms,
                "cache_hit": cache_hit,
                "success": success,
                "error": error
            }

            logger.debug(f"[Metrics] LLM Validation: {validation_type} - {latency_ms}ms (cache: {cache_hit})")

            self._send_to_langsmith("llm_validation_performance", metrics)

        except Exception as e:
            logger.error(f"Failed to track LLM validation performance: {e}")

    def complete_query(self, session_id: str, query_id: str):
        """Mark query as complete and increment counter"""
        try:
            self._session_metrics[session_id]["queries_processed"] += 1
        except Exception as e:
            logger.error(f"Failed to complete query metrics: {e}")

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Get aggregated metrics for a session

        Returns:
            Dictionary with session metrics summary
        """
        try:
            metrics = self._session_metrics.get(session_id, {})

            if not metrics or metrics["queries_processed"] == 0:
                return {"session_id": session_id, "no_data": True}

            confidence_scores = metrics.get("confidence_scores", [])
            avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0

            return {
                "session_id": session_id,
                "queries_processed": metrics["queries_processed"],
                "input_blocks": metrics["input_guardrail_triggers"],
                "output_flags": metrics["output_guardrail_triggers"],
                "fact_verification_flags": metrics["fact_verification_flags"],
                "llm_validations_total": metrics["llm_validations_performed"],
                "average_confidence_score": round(avg_confidence, 3),
                "total_processing_time_ms": metrics["total_processing_time_ms"],
                "avg_processing_time_ms": metrics["total_processing_time_ms"] // metrics["queries_processed"] if metrics["queries_processed"] > 0 else 0
            }

        except Exception as e:
            logger.error(f"Failed to get session summary: {e}")
            return {"session_id": session_id, "error": str(e)}

    def _send_to_langsmith(self, event_type: str, metrics: Dict[str, Any]):
        """
        Send metrics to LangSmith as run metadata

        Note: In production, this would be integrated with actual LangSmith runs.
        For now, we just log the intent to send.
        """
        try:
            # In production, this would use the actual run_id from the query processing
            logger.debug(f"[LangSmith] Would send {event_type} metrics: {metrics.get('query_id')}")

            # Future: self.langsmith_client.update_run(run_id, extra=metrics)

        except Exception as e:
            logger.debug(f"Failed to send metrics to LangSmith: {e}")

    def send_confidence_feedback(self, run_id: str, confidence_score: float, verification_details: Dict[str, Any]):
        """
        Send confidence score as feedback to LangSmith run

        Args:
            run_id: LangSmith run ID
            confidence_score: Verification confidence score (0.0-1.0)
            verification_details: Additional verification details
        """
        try:
            if not run_id:
                return

            # Send as numeric feedback (0.0-1.0 scale matches LangSmith)
            self.langsmith_client.create_feedback(
                run_id=run_id,
                key="fact_verification_confidence",
                score=confidence_score,
                comment=json.dumps(verification_details)
            )

            logger.info(f"[LangSmith] Sent confidence feedback: {confidence_score:.3f} for run {run_id}")

        except Exception as e:
            logger.error(f"Failed to send confidence feedback to LangSmith: {e}")


# Global metrics tracker instance
guardrail_metrics = GuardrailMetricsTracker()
