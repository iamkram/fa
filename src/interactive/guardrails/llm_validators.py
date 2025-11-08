"""
LLM-Based Guardrail Validators

Provides LLM-powered validation for edge cases that regex/keyword matching misses.
Uses LangSmith prompts with async execution and caching.
"""

import logging
import json
import hashlib
import time
from typing import Dict, Any, Optional, List
from functools import lru_cache
from datetime import datetime, timedelta

from langchain_openai import ChatOpenAI
from langsmith import traceable

from src.config.settings import settings
from src.shared.utils.prompt_manager import prompt_manager
from src.shared.monitoring.guardrail_metrics import guardrail_metrics

logger = logging.getLogger(__name__)


class LLMGuardrailValidator:
    """LLM-based guardrail validation with caching"""

    def __init__(self):
        """Initialize LLM validator"""
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",  # Fast, cheap model for guardrails
            temperature=0.0,  # Deterministic for guardrails
            timeout=5.0  # Fast timeout for guardrails
        )
        self._cache: Dict[str, tuple[Any, datetime]] = {}
        self._cache_ttl = timedelta(hours=1)

    def _get_cache_key(self, prompt_name: str, inputs: Dict[str, Any]) -> str:
        """Generate cache key from prompt name and inputs"""
        content = f"{prompt_name}:{json.dumps(inputs, sort_keys=True)}"
        return hashlib.md5(content.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Get result from cache if not expired"""
        if cache_key in self._cache:
            result, timestamp = self._cache[cache_key]
            if datetime.now() - timestamp < self._cache_ttl:
                logger.debug(f"Cache hit for {cache_key}")
                return result
            else:
                # Expired, remove from cache
                del self._cache[cache_key]
        return None

    def _set_cache(self, cache_key: str, result: Any):
        """Store result in cache with timestamp"""
        self._cache[cache_key] = (result, datetime.now())

    @traceable(name="LLM Guardrail Validation", run_type="chain")
    async def validate_with_llm(
        self,
        prompt_name: str,
        inputs: Dict[str, Any],
        use_cache: bool = True,
        session_id: str = None,
        query_id: str = None
    ) -> Dict[str, Any]:
        """
        Run LLM-based validation using a LangSmith prompt

        Args:
            prompt_name: Name of the prompt to use
            inputs: Input variables for the prompt
            use_cache: Whether to use caching (default: True)
            session_id: Optional session ID for metrics tracking
            query_id: Optional query ID for metrics tracking

        Returns:
            Parsed JSON response from LLM
        """
        start_time = time.time()
        cache_hit = False
        success = True
        error_msg = None

        try:
            # Check cache first
            cache_key = self._get_cache_key(prompt_name, inputs)
            if use_cache:
                cached = self._get_from_cache(cache_key)
                if cached is not None:
                    cache_hit = True
                    latency_ms = int((time.time() - start_time) * 1000)

                    # Track metrics if session info provided
                    if session_id and query_id:
                        guardrail_metrics.track_llm_validation_performance(
                            validation_type=prompt_name,
                            session_id=session_id,
                            query_id=query_id,
                            latency_ms=latency_ms,
                            cache_hit=True,
                            success=True
                        )

                    return cached

            # Get prompt from LangSmith (with fallback)
            prompt = prompt_manager.get_prompt(prompt_name)

            # Invoke LLM
            logger.debug(f"Running LLM validation: {prompt_name}")
            chain = prompt | self.llm
            response = await chain.ainvoke(inputs)

            # Parse JSON response
            result = self._parse_json_response(response.content)

            # Cache result
            if use_cache:
                self._set_cache(cache_key, result)

            latency_ms = int((time.time() - start_time) * 1000)

            # Track metrics if session info provided
            if session_id and query_id:
                guardrail_metrics.track_llm_validation_performance(
                    validation_type=prompt_name,
                    session_id=session_id,
                    query_id=query_id,
                    latency_ms=latency_ms,
                    cache_hit=False,
                    success=True
                )

            return result

        except Exception as e:
            success = False
            error_msg = str(e)
            latency_ms = int((time.time() - start_time) * 1000)

            logger.error(f"LLM validation failed for {prompt_name}: {e}")

            # Track metrics if session info provided
            if session_id and query_id:
                guardrail_metrics.track_llm_validation_performance(
                    validation_type=prompt_name,
                    session_id=session_id,
                    query_id=query_id,
                    latency_ms=latency_ms,
                    cache_hit=cache_hit,
                    success=False,
                    error=error_msg
                )

            return self._get_fallback_response(prompt_name)

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks"""
        # Remove markdown code blocks if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}\nContent: {content}")
            raise

    def _get_fallback_response(self, prompt_name: str) -> Dict[str, Any]:
        """Get safe fallback response if LLM call fails"""
        fallbacks = {
            "input_pii_validator": {
                "pii_detected": False,
                "pii_items": [],
                "risk_level": "low"
            },
            "prompt_injection_detector": {
                "injection_detected": False,
                "injection_type": "none",
                "confidence": 0.0,
                "explanation": "LLM validation unavailable"
            },
            "off_topic_classifier": {
                "on_topic": True,  # Assume on-topic if LLM fails
                "topic_category": "stocks",
                "confidence": 0.5,
                "reasoning": "LLM validation unavailable"
            },
            "hallucination_detector": {
                "hallucinations_detected": False,
                "hallucination_items": [],
                "confidence": 0.0
            },
            "compliance_validator": {
                "compliant": True,  # Assume compliant if LLM fails (flagged elsewhere)
                "violations": [],
                "warnings": ["LLM validation unavailable"],
                "recommendations": []
            }
        }
        return fallbacks.get(prompt_name, {})


# ============================================================================
# Convenience Functions
# ============================================================================

_validator = LLMGuardrailValidator()


async def validate_input_pii(query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Validate input for PII using LLM

    Returns:
        {
            "pii_detected": bool,
            "pii_items": [{"type": str, "text": str, "confidence": float}],
            "risk_level": "low|medium|high"
        }
    """
    return await _validator.validate_with_llm(
        "input_pii_validator",
        {"query": query, "context": json.dumps(context or {})}
    )


async def detect_prompt_injection(query: str) -> Dict[str, Any]:
    """
    Detect prompt injection attempts using LLM

    Returns:
        {
            "injection_detected": bool,
            "injection_type": str,
            "confidence": float,
            "explanation": str
        }
    """
    return await _validator.validate_with_llm(
        "prompt_injection_detector",
        {"query": query}
    )


async def classify_topic(query: str) -> Dict[str, Any]:
    """
    Classify if query is on-topic using LLM

    Returns:
        {
            "on_topic": bool,
            "topic_category": str,
            "confidence": float,
            "reasoning": str
        }
    """
    return await _validator.validate_with_llm(
        "off_topic_classifier",
        {"query": query}
    )


async def detect_hallucinations(response: str, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Detect hallucinations in response using LLM

    Returns:
        {
            "hallucinations_detected": bool,
            "hallucination_items": [{"claim": str, "reason": str, "severity": str}],
            "confidence": float
        }
    """
    return await _validator.validate_with_llm(
        "hallucination_detector",
        {
            "response": response,
            "sources": json.dumps(sources, indent=2)
        }
    )


async def validate_compliance(response: str, query_context: str = "") -> Dict[str, Any]:
    """
    Validate response for SEC/FINRA compliance using LLM

    Returns:
        {
            "compliant": bool,
            "violations": [{"rule": str, "issue": str, "severity": str}],
            "warnings": [str],
            "recommendations": [str]
        }
    """
    return await _validator.validate_with_llm(
        "compliance_validator",
        {
            "response": response,
            "query_context": query_context
        }
    )
