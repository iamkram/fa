"""
Tests for Guardrail Metrics Tracker

Tests the comprehensive metrics tracking system for guardrails.
"""

import pytest
from src.shared.monitoring.guardrail_metrics import GuardrailMetricsTracker


class TestGuardrailMetricsTracker:
    """Test suite for GuardrailMetricsTracker"""

    @pytest.fixture
    def tracker(self):
        """Create a fresh metrics tracker for each test"""
        return GuardrailMetricsTracker()

    @pytest.fixture
    def sample_flags(self):
        """Sample guardrail flags for testing"""
        return ["flag1", "flag2", "flag3"]

    def test_tracker_initialization(self, tracker):
        """Test tracker initializes with empty metrics"""
        assert tracker._session_metrics is not None
        assert len(tracker._session_metrics) == 0

    def test_track_input_guardrail(self, tracker, sample_flags):
        """Test tracking input guardrail events"""
        session_id = "test-session-1"
        query_id = "query-123"

        # Track a blocked input
        tracker.track_input_guardrail(
            session_id=session_id,
            query_id=query_id,
            flags=sample_flags,
            input_safe=False,
            llm_performed=True,
            processing_time_ms=150
        )

        # Verify metrics were recorded
        assert session_id in tracker._session_metrics
        metrics = tracker._session_metrics[session_id]
        assert metrics["input_guardrail_triggers"] == 1
        assert metrics["llm_validations_performed"] == 1
        assert metrics["total_processing_time_ms"] == 150

    def test_track_output_guardrail(self, tracker):
        """Test tracking output guardrail events"""
        session_id = "test-session-2"
        query_id = "query-456"

        # Track output with violations
        tracker.track_output_guardrail(
            session_id=session_id,
            query_id=query_id,
            flags=["pii", "hallucination"],
            output_safe=False,
            llm_performed=True,
            processing_time_ms=200,
            pii_count=2,
            hallucination_count=1,
            compliance_count=0
        )

        # Verify metrics
        metrics = tracker._session_metrics[session_id]
        assert metrics["output_guardrail_triggers"] == 1
        assert metrics["llm_validations_performed"] == 1
        assert metrics["total_processing_time_ms"] == 200

    def test_track_fact_verification(self, tracker):
        """Test tracking fact verification events"""
        session_id = "test-session-3"
        query_id = "query-789"

        # Track verification with low confidence
        tracker.track_fact_verification(
            session_id=session_id,
            query_id=query_id,
            confidence_score=0.7,
            verification_passed=False,
            llm_performed=True,
            source_count=5,
            hallucination_details=[{"claim": "test", "reason": "unsupported"}],
            processing_time_ms=300
        )

        # Verify metrics
        metrics = tracker._session_metrics[session_id]
        assert metrics["fact_verification_flags"] == 1
        assert metrics["confidence_scores"] == [0.7]
        assert metrics["llm_validations_performed"] == 1
        assert metrics["total_processing_time_ms"] == 300

    def test_track_llm_validation_performance(self, tracker):
        """Test tracking LLM validation performance"""
        session_id = "test-session-4"
        query_id = "query-101"

        # Track successful LLM validation
        tracker.track_llm_validation_performance(
            validation_type="pii_detection",
            session_id=session_id,
            query_id=query_id,
            latency_ms=50,
            cache_hit=True,
            success=True
        )

        # Should not fail (just logs)
        assert True  # Test passes if no exception

    def test_get_session_summary_empty(self, tracker):
        """Test getting summary for non-existent session"""
        summary = tracker.get_session_summary("non-existent")
        assert summary["session_id"] == "non-existent"
        assert summary.get("no_data") is True

    def test_get_session_summary_with_data(self, tracker):
        """Test getting summary with actual metrics"""
        session_id = "test-session-5"
        query_id = "query-202"

        # Add some metrics
        tracker.track_input_guardrail(
            session_id=session_id,
            query_id=query_id,
            flags=[],
            input_safe=True,
            llm_performed=False,
            processing_time_ms=100
        )
        tracker.complete_query(session_id, query_id)

        tracker.track_fact_verification(
            session_id=session_id,
            query_id=query_id,
            confidence_score=0.95,
            verification_passed=True,
            llm_performed=True,
            source_count=3,
            processing_time_ms=150
        )
        tracker.complete_query(session_id, query_id)

        # Get summary
        summary = tracker.get_session_summary(session_id)
        assert summary["session_id"] == session_id
        assert summary["queries_processed"] == 2
        assert summary["input_blocks"] == 0
        assert summary["average_confidence_score"] == 0.95
        assert summary["total_processing_time_ms"] == 250

    def test_multiple_sessions(self, tracker):
        """Test tracking multiple sessions independently"""
        # Session 1
        tracker.track_input_guardrail(
            session_id="session-1",
            query_id="q1",
            flags=[],
            input_safe=True,
            llm_performed=False,
            processing_time_ms=100
        )

        # Session 2
        tracker.track_input_guardrail(
            session_id="session-2",
            query_id="q2",
            flags=["pii"],
            input_safe=False,
            llm_performed=True,
            processing_time_ms=200
        )

        # Verify independent tracking
        assert tracker._session_metrics["session-1"]["input_guardrail_triggers"] == 0
        assert tracker._session_metrics["session-2"]["input_guardrail_triggers"] == 1

    def test_complete_query(self, tracker):
        """Test completing queries increments counter"""
        session_id = "test-session-6"

        # Complete 3 queries
        for i in range(3):
            tracker.complete_query(session_id, f"query-{i}")

        # Verify count
        metrics = tracker._session_metrics[session_id]
        assert metrics["queries_processed"] == 3

    def test_confidence_score_averaging(self, tracker):
        """Test averaging multiple confidence scores"""
        session_id = "test-session-7"

        # Add multiple confidence scores
        scores = [0.8, 0.9, 0.85, 0.95]
        for i, score in enumerate(scores):
            tracker.track_fact_verification(
                session_id=session_id,
                query_id=f"query-{i}",
                confidence_score=score,
                verification_passed=True,
                llm_performed=True,
                source_count=3,
                processing_time_ms=100
            )
            tracker.complete_query(session_id, f"query-{i}")

        # Get summary
        summary = tracker.get_session_summary(session_id)
        expected_avg = sum(scores) / len(scores)
        assert summary["average_confidence_score"] == round(expected_avg, 3)


def test_module_level_instance():
    """Test that module exports a global instance"""
    from src.shared.monitoring.guardrail_metrics import guardrail_metrics
    assert guardrail_metrics is not None
    assert isinstance(guardrail_metrics, GuardrailMetricsTracker)
