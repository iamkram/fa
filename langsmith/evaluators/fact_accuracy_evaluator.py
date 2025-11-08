"""
Fact Accuracy Evaluator for LangSmith

Evaluates factual accuracy of generated summaries against ground truth data.
Used in CI/CD for regression testing and continuous evaluation.
"""

import logging
from typing import Dict, Any, Optional
from langsmith.evaluation import evaluator
from langchain_anthropic import ChatAnthropic

from src.config.settings import settings

logger = logging.getLogger(__name__)


@evaluator
def fact_accuracy_evaluator(run: Any, example: Any) -> Dict[str, Any]:
    """Evaluate factual accuracy of a summary

    Args:
        run: LangSmith run object containing the generated summary
        example: LangSmith example object containing ground truth

    Returns:
        Dict with score (0.0-1.0) and reasoning
    """
    # Extract generated summary and ground truth
    generated_summary = run.outputs.get("response_text", "")
    ground_truth = example.outputs.get("expected_summary", "")
    source_data = example.inputs.get("source_data", "")

    if not generated_summary or not ground_truth:
        return {
            "key": "fact_accuracy",
            "score": 0.0,
            "comment": "Missing generated summary or ground truth"
        }

    # Use LLM to evaluate factual accuracy
    llm = ChatAnthropic(
        model="claude-3-5-sonnet-20241022",
        anthropic_api_key=settings.anthropic_api_key,
        temperature=0.0
    )

    prompt = f"""You are evaluating the factual accuracy of a generated stock summary.

Ground Truth Summary:
{ground_truth}

Generated Summary:
{generated_summary}

Source Data (for reference):
{source_data[:2000]}...

Task: Evaluate the factual accuracy of the generated summary by comparing it to the ground truth.

Criteria:
1. Are the key facts present in both summaries?
2. Are there any factual errors or contradictions?
3. Are numerical values (revenue, earnings, percentages) accurate?
4. Are dates and timeframes correct?
5. Are forward-looking statements consistent?

Respond with a JSON object:
{{
  "score": 0.0-1.0,
  "reasoning": "detailed explanation",
  "factual_errors": ["list any factual errors"],
  "missing_facts": ["list important facts missing from generated summary"],
  "added_facts": ["list facts in generated summary not in ground truth"]
}}
"""

    try:
        response = llm.invoke(prompt)
        response_text = response.content

        # Parse response (simple extraction)
        import json
        import re
        json_match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)

        if json_match:
            result = json.loads(json_match.group())
            score = float(result.get("score", 0.5))
            reasoning = result.get("reasoning", "")
            errors = result.get("factual_errors", [])
            missing = result.get("missing_facts", [])

            # Build detailed comment
            comment_parts = [reasoning]
            if errors:
                comment_parts.append(f"Factual Errors: {', '.join(errors)}")
            if missing:
                comment_parts.append(f"Missing Facts: {', '.join(missing)}")

            return {
                "key": "fact_accuracy",
                "score": score,
                "comment": " | ".join(comment_parts)
            }
        else:
            return {
                "key": "fact_accuracy",
                "score": 0.5,
                "comment": "Could not parse evaluator response"
            }

    except Exception as e:
        logger.error(f"Fact accuracy evaluation failed: {e}")
        return {
            "key": "fact_accuracy",
            "score": 0.0,
            "comment": f"Evaluation error: {str(e)}"
        }


@evaluator
def citation_quality_evaluator(run: Any, example: Any) -> Dict[str, Any]:
    """Evaluate quality and relevance of citations

    Args:
        run: LangSmith run object
        example: LangSmith example object

    Returns:
        Dict with score and reasoning
    """
    citations = run.outputs.get("citations", [])
    generated_summary = run.outputs.get("response_text", "")

    if not citations:
        return {
            "key": "citation_quality",
            "score": 0.0,
            "comment": "No citations provided"
        }

    # Check citation count
    citation_count = len(citations)

    # Check if citations are relevant
    llm = ChatAnthropic(
        model="claude-3-5-haiku-20241022",  # Faster for this task
        anthropic_api_key=settings.anthropic_api_key,
        temperature=0.0
    )

    prompt = f"""Evaluate the quality of citations for this summary.

Summary:
{generated_summary}

Citations ({citation_count} total):
{chr(10).join(f"{i+1}. {c.get('claim_text', '')} -> {c.get('source_type', '')}" for i, c in enumerate(citations[:10]))}

Criteria:
1. Are claims properly cited?
2. Are citations from credible sources?
3. Is citation density appropriate (not too few, not too many)?

Respond with a JSON object:
{{
  "score": 0.0-1.0,
  "reasoning": "brief explanation"
}}
"""

    try:
        response = llm.invoke(prompt)
        response_text = response.content

        import json
        import re
        json_match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)

        if json_match:
            result = json.loads(json_match.group())
            score = float(result.get("score", 0.5))
            reasoning = result.get("reasoning", "")

            return {
                "key": "citation_quality",
                "score": score,
                "comment": f"{reasoning} ({citation_count} citations)"
            }
        else:
            return {
                "key": "citation_quality",
                "score": 0.5,
                "comment": f"{citation_count} citations provided"
            }

    except Exception as e:
        return {
            "key": "citation_quality",
            "score": 0.5,
            "comment": f"{citation_count} citations, evaluation error: {str(e)}"
        }


@evaluator
def word_count_evaluator(run: Any, example: Any) -> Dict[str, Any]:
    """Evaluate if word count is within target range

    Args:
        run: LangSmith run object
        example: LangSmith example object

    Returns:
        Dict with score and reasoning
    """
    response_text = run.outputs.get("response_text", "")
    response_tier = run.outputs.get("response_tier", "medium")

    word_count = len(response_text.split())

    # Target ranges by tier
    target_ranges = {
        "hook": (25, 50),
        "medium": (100, 150),
        "expanded": (200, 250)
    }

    min_words, max_words = target_ranges.get(response_tier, (100, 150))

    # Calculate score
    if min_words <= word_count <= max_words:
        score = 1.0
        comment = f"Perfect: {word_count} words (target: {min_words}-{max_words})"
    elif word_count < min_words:
        # Too short
        deficit = min_words - word_count
        score = max(0.0, 1.0 - (deficit / min_words))
        comment = f"Too short: {word_count} words (target: {min_words}-{max_words})"
    else:
        # Too long
        excess = word_count - max_words
        score = max(0.0, 1.0 - (excess / max_words))
        comment = f"Too long: {word_count} words (target: {min_words}-{max_words})"

    return {
        "key": "word_count",
        "score": score,
        "comment": comment
    }


@evaluator
def response_time_evaluator(run: Any, example: Any) -> Dict[str, Any]:
    """Evaluate if response time meets SLA

    Args:
        run: LangSmith run object
        example: LangSmith example object

    Returns:
        Dict with score and reasoning
    """
    response_time_ms = run.outputs.get("processing_time_ms", 0)
    response_tier = run.outputs.get("response_tier", "standard")

    # SLA thresholds by tier (milliseconds)
    sla_thresholds = {
        "quick": 1000,      # 1s for quick answers
        "standard": 3000,   # 3s for standard queries
        "deep": 10000       # 10s for deep research
    }

    threshold_ms = sla_thresholds.get(response_tier, 3000)

    # Calculate score
    if response_time_ms <= threshold_ms:
        score = 1.0
        comment = f"Met SLA: {response_time_ms}ms (target: <{threshold_ms}ms)"
    else:
        # Exceeded SLA
        excess = response_time_ms - threshold_ms
        score = max(0.0, 1.0 - (excess / threshold_ms))
        comment = f"Exceeded SLA: {response_time_ms}ms (target: <{threshold_ms}ms)"

    return {
        "key": "response_time",
        "score": score,
        "comment": comment
    }


@evaluator
def guardrail_pass_evaluator(run: Any, example: Any) -> Dict[str, Any]:
    """Evaluate if response passed all guardrails

    Args:
        run: LangSmith run object
        example: LangSmith example object

    Returns:
        Dict with score and reasoning
    """
    guardrail_status = run.outputs.get("guardrail_status", "unknown")
    pii_flags = run.outputs.get("pii_flags", [])

    if guardrail_status == "passed":
        score = 1.0
        comment = "All guardrails passed"
    elif guardrail_status == "failed":
        score = 0.0
        comment = f"Guardrails failed: {', '.join(pii_flags) if pii_flags else 'unknown reason'}"
    else:
        score = 0.0
        comment = "Guardrail status unknown"

    return {
        "key": "guardrail_pass",
        "score": score,
        "comment": comment
    }
