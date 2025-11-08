"""Tests for output guardrails node"""

import pytest
from unittest.mock import patch, AsyncMock
from src.interactive.state import InteractiveGraphState, GuardrailFlag
from src.interactive.nodes.output_guardrails import output_guardrail_node


def test_pii_detected_in_output():
    """Test that PII in output is flagged"""
    state = InteractiveGraphState(
        query_id="test",
        fa_id="FA-123",
        session_id="session-1",
        query_text="What are my account details?",
        query_type="chat",
        response_text="Your account number is 12345678 and SSN is 123-45-6789."
    )

    with patch('src.interactive.nodes.output_guardrails.asyncio.run') as mock_run:
        # Mock LLM to return no issues
        mock_run.return_value = {
            "hallucination": {"hallucinations_detected": False, "hallucination_items": []},
            "compliance": {"compliant": True, "violations": [], "warnings": []}
        }

        result = output_guardrail_node(state, {})

    # Should flag PII in output (regex detection)
    assert len(result["output_flags"]) > 0
    pii_flags = [f for f in result["output_flags"] if f.flag_type == "pii"]
    assert len(pii_flags) > 0
    assert len(result["pii_flags"]) > 0


def test_hallucination_indicators_detected():
    """Test that hallucination indicators are flagged"""
    state = InteractiveGraphState(
        query_id="test",
        fa_id="FA-123",
        session_id="session-1",
        query_text="What's happening with AAPL?",
        query_type="chat",
        response_text="I believe AAPL will probably go up, but I think it might be risky."
    )

    with patch('src.interactive.nodes.output_guardrails.asyncio.run') as mock_run:
        # Mock LLM to return no issues
        mock_run.return_value = {
            "hallucination": {"hallucinations_detected": False, "hallucination_items": []},
            "compliance": {"compliant": True, "violations": [], "warnings": []}
        }

        result = output_guardrail_node(state, {})

    # Should flag hallucination indicators (keywords)
    hallucination_flags = [f for f in result["output_flags"] if f.flag_type == "hallucination"]
    assert len(hallucination_flags) > 0


def test_compliance_violations_detected():
    """Test that compliance violations are flagged"""
    state = InteractiveGraphState(
        query_id="test",
        fa_id="FA-123",
        session_id="session-1",
        query_text="Can I trust this stock?",
        query_type="chat",
        response_text="This investment has guaranteed returns and cannot lose value."
    )

    with patch('src.interactive.nodes.output_guardrails.asyncio.run') as mock_run:
        # Mock LLM to return no issues
        mock_run.return_value = {
            "hallucination": {"hallucinations_detected": False, "hallucination_items": []},
            "compliance": {"compliant": True, "violations": [], "warnings": []}
        }

        result = output_guardrail_node(state, {})

    # Should flag compliance violations (keywords)
    compliance_flags = [f for f in result["output_flags"] if f.flag_type == "compliance"]
    assert len(compliance_flags) > 0


def test_llm_hallucination_detection():
    """Test LLM-based hallucination detection"""
    state = InteractiveGraphState(
        query_id="test",
        fa_id="FA-123",
        session_id="session-1",
        query_text="What are Apple's earnings?",
        query_type="chat",
        response_text="Apple's Q3 earnings were $500 billion, showing 1000% growth.",
        retrieved_docs=[
            {"type": "earnings", "content": "Apple's Q3 earnings were $89.5 billion."}
        ]
    )

    with patch('src.interactive.nodes.output_guardrails.asyncio.run') as mock_run:
        # Mock LLM to detect hallucinations
        mock_run.return_value = {
            "hallucination": {
                "hallucinations_detected": True,
                "hallucination_items": [
                    {
                        "claim": "earnings were $500 billion",
                        "reason": "Actual earnings were $89.5 billion",
                        "severity": "high"
                    },
                    {
                        "claim": "1000% growth",
                        "reason": "No source supports this claim",
                        "severity": "high"
                    }
                ]
            },
            "compliance": {"compliant": True, "violations": [], "warnings": []}
        }

        result = output_guardrail_node(state, {})

    # Should flag LLM-detected hallucinations
    hallucination_flags = [f for f in result["output_flags"] if f.flag_type == "hallucination"]
    assert len(hallucination_flags) >= 2
    assert any("high" in f.severity for f in hallucination_flags)


def test_llm_compliance_validation():
    """Test LLM-based compliance validation"""
    state = InteractiveGraphState(
        query_id="test",
        fa_id="FA-123",
        session_id="session-1",
        query_text="Should I buy this stock?",
        query_type="chat",
        response_text="You should definitely buy AAPL now before it's too late!"
    )

    with patch('src.interactive.nodes.output_guardrails.asyncio.run') as mock_run:
        # Mock LLM to detect compliance violations
        mock_run.return_value = {
            "hallucination": {"hallucinations_detected": False, "hallucination_items": []},
            "compliance": {
                "compliant": False,
                "violations": [
                    {
                        "rule": "FINRA 2111 (Suitability)",
                        "issue": "Direct recommendation without suitability assessment",
                        "severity": "high"
                    }
                ],
                "warnings": ["Avoid using urgent language"]
            }
        }

        result = output_guardrail_node(state, {})

    # Should flag LLM-detected compliance violations
    compliance_flags = [f for f in result["output_flags"] if f.flag_type == "compliance"]
    assert len(compliance_flags) >= 1


def test_clean_output_passes():
    """Test that clean output passes all guardrails"""
    state = InteractiveGraphState(
        query_id="test",
        fa_id="FA-123",
        session_id="session-1",
        query_text="What are Apple's latest earnings?",
        query_type="chat",
        response_text="According to the latest earnings report, Apple's Q3 revenue was $89.5 billion."
    )

    with patch('src.interactive.nodes.output_guardrails.asyncio.run') as mock_run:
        # Mock LLM to return no issues
        mock_run.return_value = {
            "hallucination": {"hallucinations_detected": False, "hallucination_items": []},
            "compliance": {"compliant": True, "violations": [], "warnings": []}
        }

        result = output_guardrail_node(state, {})

    # Should pass with no flags
    assert result["output_safe"] == True
    assert result["guardrail_status"] == "passed"
    assert len(result["output_flags"]) == 0


def test_empty_response_handling():
    """Test handling of empty response"""
    state = InteractiveGraphState(
        query_id="test",
        fa_id="FA-123",
        session_id="session-1",
        query_text="What is AAPL?",
        query_type="chat",
        response_text=""
    )

    result = output_guardrail_node(state, {})

    # Should handle empty response gracefully
    assert result["output_safe"] == True


def test_multiple_violations():
    """Test handling multiple violation types"""
    state = InteractiveGraphState(
        query_id="test",
        fa_id="FA-123",
        session_id="session-1",
        query_text="Tell me about my account",
        query_type="chat",
        response_text="I believe your account 12345678 has guaranteed returns and insider information suggests big gains."
    )

    with patch('src.interactive.nodes.output_guardrails.asyncio.run') as mock_run:
        # Mock LLM to return multiple issues
        mock_run.return_value = {
            "hallucination": {
                "hallucinations_detected": True,
                "hallucination_items": [
                    {
                        "claim": "guaranteed returns",
                        "reason": "Cannot guarantee returns",
                        "severity": "medium"
                    }
                ]
            },
            "compliance": {
                "compliant": False,
                "violations": [
                    {
                        "rule": "SEC Rule 10b-5",
                        "issue": "Reference to insider information",
                        "severity": "high"
                    }
                ],
                "warnings": []
            }
        }

        result = output_guardrail_node(state, {})

    # Should have multiple flag types
    assert len(result["output_flags"]) >= 3  # PII + hallucination + compliance
    flag_types = set(f.flag_type for f in result["output_flags"])
    assert "pii" in flag_types
    assert "hallucination" in flag_types
    assert "compliance" in flag_types


def test_llm_failure_fallback():
    """Test graceful handling when LLM validation fails"""
    state = InteractiveGraphState(
        query_id="test",
        fa_id="FA-123",
        session_id="session-1",
        query_text="What are AAPL earnings?",
        query_type="chat",
        response_text="Apple's earnings are strong this quarter."
    )

    with patch('src.interactive.nodes.output_guardrails.asyncio.run') as mock_run:
        # Mock LLM to raise an exception
        mock_run.side_effect = Exception("LLM API error")

        result = output_guardrail_node(state, {})

    # Should continue with keyword checks only
    assert result["output_safe"] == True  # No keyword violations
    assert result["guardrail_status"] == "passed"
