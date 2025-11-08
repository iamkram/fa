"""Tests for fact verification node"""

import pytest
from unittest.mock import patch, MagicMock
from src.interactive.state import InteractiveGraphState
from src.interactive.nodes.fact_verification import fact_verification_node


def test_keyword_unsupported_claims():
    """Test detection of unsupported claim keywords"""
    state = InteractiveGraphState(
        query_id="test",
        fa_id="FA-123",
        session_id="session-1",
        query_text="Should I invest?",
        query_type="chat",
        response_text="This investment will definitely guarantee 100% returns and is risk-free."
    )

    with patch('src.interactive.nodes.fact_verification.asyncio.run') as mock_run:
        # Mock LLM to return no hallucinations
        mock_run.return_value = {
            "hallucinations_detected": False,
            "hallucination_items": [],
            "confidence": 0.9
        }

        result = fact_verification_node(state, {})

    # Should detect unsupported claim keywords
    assert result["confidence_score"] < 0.95  # Penalties applied
    assert len(result["flags"]) > 0
    assert any("guarantee" in flag or "risk-free" in flag for flag in result["flags"])


def test_excessive_numbers_without_citations():
    """Test flagging of many numbers without citations"""
    state = InteractiveGraphState(
        query_id="test",
        fa_id="FA-123",
        session_id="session-1",
        query_text="What are the financials?",
        query_type="chat",
        response_text="The stock price is $150.25, market cap is $2.5T, revenue is $89.5B, "
                      "profit is $25.3B, and PE ratio is 28.5 with no sources mentioned."
    )

    with patch('src.interactive.nodes.fact_verification.asyncio.run') as mock_run:
        # Mock LLM to return no hallucinations
        mock_run.return_value = {
            "hallucinations_detected": False,
            "hallucination_items": [],
            "confidence": 0.9
        }

        result = fact_verification_node(state, {})

    # Should apply penalty for many numbers without citations
    assert result["confidence_score"] < 0.95


def test_numbers_with_citations_okay():
    """Test that numbers with citations don't get penalized"""
    state = InteractiveGraphState(
        query_id="test",
        fa_id="FA-123",
        session_id="session-1",
        query_text="What are the financials?",
        query_type="chat",
        response_text="According to the Q3 report, revenue was $89.5B and profit was $25.3B. "
                      "Per the earnings call, market cap is $2.5T based on latest data."
    )

    with patch('src.interactive.nodes.fact_verification.asyncio.run') as mock_run:
        # Mock LLM to return no hallucinations
        mock_run.return_value = {
            "hallucinations_detected": False,
            "hallucination_items": [],
            "confidence": 0.9
        }

        result = fact_verification_node(state, {})

    # Should not penalize because of citation markers
    assert result["confidence_score"] >= 0.90


def test_llm_hallucination_high_severity():
    """Test LLM-detected high severity hallucinations"""
    state = InteractiveGraphState(
        query_id="test",
        fa_id="FA-123",
        session_id="session-1",
        query_text="What are Apple's earnings?",
        query_type="chat",
        response_text="Apple's revenue was $500 billion in Q3."
    )

    # Mock assembled_context with source data
    mock_context = MagicMock()
    mock_context.batch_summary = {"text": "Apple Q3 revenue: $89.5 billion"}
    state.assembled_context = mock_context

    with patch('src.interactive.nodes.fact_verification.extract_sources_from_context') as mock_extract:
        with patch('src.interactive.nodes.fact_verification.asyncio.run') as mock_run:
            # Mock source extraction
            mock_extract.return_value = [{"type": "batch", "content": "Apple Q3: $89.5B"}]

            # Mock LLM to detect severe hallucination
            mock_run.return_value = {
                "hallucinations_detected": True,
                "hallucination_items": [
                    {
                        "claim": "revenue was $500 billion",
                        "reason": "Source states $89.5 billion, not $500 billion",
                        "severity": "high"
                    }
                ],
                "confidence": 0.3
            }

            result = fact_verification_node(state, {})

    # Should fail verification with low confidence
    assert result["verification_passed"] == False
    assert result["confidence_score"] < 0.8
    assert result["llm_verification_performed"] == True
    assert len(result["hallucination_details"]) == 1
    assert result["hallucination_details"][0]["severity"] == "high"


def test_llm_hallucination_medium_severity():
    """Test LLM-detected medium severity hallucinations"""
    state = InteractiveGraphState(
        query_id="test",
        fa_id="FA-123",
        session_id="session-1",
        query_text="How is Apple doing?",
        query_type="chat",
        response_text="Apple's growth rate is trending upward significantly."
    )

    # Mock assembled_context
    mock_context = MagicMock()
    state.assembled_context = mock_context

    with patch('src.interactive.nodes.fact_verification.extract_sources_from_context') as mock_extract:
        with patch('src.interactive.nodes.fact_verification.asyncio.run') as mock_run:
            # Mock source extraction
            mock_extract.return_value = [{"type": "batch", "content": "Apple growth: moderate"}]

            # Mock LLM to detect medium hallucination
            mock_run.return_value = {
                "hallucinations_detected": True,
                "hallucination_items": [
                    {
                        "claim": "significantly trending upward",
                        "reason": "Source describes moderate increase, not significant",
                        "severity": "medium"
                    }
                ],
                "confidence": 0.6
            }

            result = fact_verification_node(state, {})

    # Should be flagged but not necessarily fail
    assert result["confidence_score"] < 0.9
    assert result["llm_verification_performed"] == True
    assert len(result["hallucination_details"]) == 1


def test_llm_verification_not_run_no_sources():
    """Test that LLM verification skips when no sources available"""
    state = InteractiveGraphState(
        query_id="test",
        fa_id="FA-123",
        session_id="session-1",
        query_text="What is Apple?",
        query_type="chat",
        response_text="Apple is a technology company.",
        assembled_context=None
    )

    result = fact_verification_node(state, {})

    # Should use keyword checks only
    assert result["llm_verification_performed"] == False
    assert result["source_count"] == 0


def test_verification_passed_high_confidence():
    """Test verification passes with high confidence"""
    state = InteractiveGraphState(
        query_id="test",
        fa_id="FA-123",
        session_id="session-1",
        query_text="What are Apple's earnings?",
        query_type="chat",
        response_text="According to the latest report, Apple's Q3 revenue was $89.5 billion."
    )

    # Mock assembled_context
    mock_context = MagicMock()
    state.assembled_context = mock_context

    with patch('src.interactive.nodes.fact_verification.extract_sources_from_context') as mock_extract:
        with patch('src.interactive.nodes.fact_verification.asyncio.run') as mock_run:
            # Mock source extraction
            mock_extract.return_value = [{"type": "batch", "content": "Apple Q3 revenue: $89.5B"}]

            # Mock LLM to confirm accuracy
            mock_run.return_value = {
                "hallucinations_detected": False,
                "hallucination_items": [],
                "confidence": 0.95
            }

            result = fact_verification_node(state, {})

    # Should pass with high confidence
    assert result["verification_passed"] == True
    assert result["confidence_score"] >= 0.8
    assert result["llm_verification_performed"] == True
    assert len(result["flags"]) == 0


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

    result = fact_verification_node(state, {})

    # Should return default high confidence for empty response
    assert result["confidence_score"] == 1.0


def test_llm_failure_graceful_degradation():
    """Test graceful handling when LLM verification fails"""
    state = InteractiveGraphState(
        query_id="test",
        fa_id="FA-123",
        session_id="session-1",
        query_text="Tell me about Apple",
        query_type="chat",
        response_text="Apple's revenue is strong."
    )

    # Mock assembled_context
    mock_context = MagicMock()
    state.assembled_context = mock_context

    with patch('src.interactive.nodes.fact_verification.extract_sources_from_context') as mock_extract:
        with patch('src.interactive.nodes.fact_verification.asyncio.run') as mock_run:
            # Mock source extraction
            mock_extract.return_value = [{"type": "batch", "content": "Apple data"}]

            # Mock LLM to raise exception
            mock_run.side_effect = Exception("LLM API error")

            result = fact_verification_node(state, {})

    # Should continue with keyword checks only
    assert result["llm_verification_performed"] == False
    assert "confidence_score" in result


def test_multiple_hallucinations_cumulative_penalty():
    """Test that multiple hallucinations apply cumulative penalties"""
    state = InteractiveGraphState(
        query_id="test",
        fa_id="FA-123",
        session_id="session-1",
        query_text="What are Apple's numbers?",
        query_type="chat",
        response_text="Apple's revenue was $500B, profit was $200B, and growth was 1000%."
    )

    # Mock assembled_context
    mock_context = MagicMock()
    state.assembled_context = mock_context

    with patch('src.interactive.nodes.fact_verification.extract_sources_from_context') as mock_extract:
        with patch('src.interactive.nodes.fact_verification.asyncio.run') as mock_run:
            # Mock source extraction
            mock_extract.return_value = [{"type": "batch", "content": "Apple Q3: revenue $89.5B, profit $22.9B, growth 8%"}]

            # Mock LLM to detect multiple hallucinations
            mock_run.return_value = {
                "hallucinations_detected": True,
                "hallucination_items": [
                    {"claim": "$500B revenue", "reason": "Actually $89.5B", "severity": "high"},
                    {"claim": "$200B profit", "reason": "Actually $22.9B", "severity": "high"},
                    {"claim": "1000% growth", "reason": "Actually 8%", "severity": "high"}
                ],
                "confidence": 0.2
            }

            result = fact_verification_node(state, {})

    # Should have very low confidence with multiple high severity issues
    assert result["verification_passed"] == False
    assert result["confidence_score"] < 0.6  # Heavy penalties
    assert len(result["hallucination_details"]) == 3
