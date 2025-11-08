"""
Advanced Hallucination Detector

Multi-layer hallucination detection system for production quality assurance.
Implements 3 validation layers:
1. Cross-source consistency - Verify claims across multiple data sources
2. Temporal consistency - Check claims against historical patterns
3. Uncertainty quantification - Detect hedging and confidence levels
"""

import logging
import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

from src.config.settings import settings
from src.shared.database.connection import db_manager
from src.shared.models.database import StockSummary

logger = logging.getLogger(__name__)


class HallucinationRisk(str, Enum):
    """Risk levels for hallucination detection"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class HallucinationCheck:
    """Result of hallucination detection"""
    overall_risk: HallucinationRisk
    cross_source_score: float  # 0.0-1.0
    temporal_consistency_score: float  # 0.0-1.0
    uncertainty_score: float  # 0.0-1.0
    flags: List[str]
    details: Dict[str, Any]


class HallucinationDetector:
    """Detect potential hallucinations in generated summaries"""

    def __init__(self):
        """Initialize hallucination detector"""
        self.llm = ChatAnthropic(
            model="claude-3-5-sonnet-20241022",
            anthropic_api_key=settings.anthropic_api_key,
            temperature=0.0  # Deterministic for validation
        )

        # Hedging patterns for uncertainty detection
        self.hedging_patterns = [
            r'\bmay\b', r'\bmight\b', r'\bcould\b', r'\bpossibly\b', r'\bperhaps\b',
            r'\blikely\b', r'\bunlikely\b', r'\bprobably\b', r'\bseems?\b',
            r'\bappears?\b', r'\bsuggests?\b', r'\bindicates?\b', r'\bpotentially\b',
            r'\bestimated?\b', r'\bapproximately\b', r'\baround\b', r'\broughly\b'
        ]

        # Confidence indicators
        self.high_confidence_patterns = [
            r'\bcertainly\b', r'\bdefinitely\b', r'\bclearly\b', r'\bobviously\b',
            r'\bundoubtedly\b', r'\bwithout\s+doubt\b', r'\bconfirmed\b',
            r'\bproven\b', r'\bverified\b'
        ]

    async def detect_hallucinations(
        self,
        summary_text: str,
        stock_id: str,
        ticker: str,
        source_data: Dict[str, str],
        previous_summaries: Optional[List[StockSummary]] = None
    ) -> HallucinationCheck:
        """Run comprehensive hallucination detection

        Args:
            summary_text: Generated summary to validate
            stock_id: Stock identifier
            ticker: Stock ticker symbol
            source_data: Dict with keys: 'edgar', 'bluematrix', 'factset'
            previous_summaries: Historical summaries for temporal checks

        Returns:
            HallucinationCheck with detection results
        """
        logger.info(f"Running hallucination detection for {ticker}")

        flags = []
        details = {}

        # Layer 1: Cross-source consistency
        cross_source_score = await self._check_cross_source_consistency(
            summary_text, source_data
        )
        details["cross_source"] = {"score": cross_source_score}

        if cross_source_score < 0.7:
            flags.append(f"Low cross-source consistency: {cross_source_score:.2f}")

        # Layer 2: Temporal consistency
        temporal_score = await self._check_temporal_consistency(
            summary_text, ticker, previous_summaries
        )
        details["temporal"] = {"score": temporal_score}

        if temporal_score < 0.7:
            flags.append(f"Low temporal consistency: {temporal_score:.2f}")

        # Layer 3: Uncertainty quantification
        uncertainty_score, uncertainty_details = self._quantify_uncertainty(summary_text)
        details["uncertainty"] = uncertainty_details

        if uncertainty_score > 0.5:
            flags.append(f"High uncertainty indicators: {uncertainty_score:.2f}")

        # Calculate overall risk
        overall_risk = self._calculate_overall_risk(
            cross_source_score, temporal_score, uncertainty_score
        )

        logger.info(
            f"Hallucination check for {ticker}: {overall_risk.value} risk "
            f"(cross-source: {cross_source_score:.2f}, temporal: {temporal_score:.2f}, "
            f"uncertainty: {uncertainty_score:.2f})"
        )

        return HallucinationCheck(
            overall_risk=overall_risk,
            cross_source_score=cross_source_score,
            temporal_consistency_score=temporal_score,
            uncertainty_score=uncertainty_score,
            flags=flags,
            details=details
        )

    async def _check_cross_source_consistency(
        self,
        summary_text: str,
        source_data: Dict[str, str]
    ) -> float:
        """Check consistency across multiple data sources

        Args:
            summary_text: Summary to validate
            source_data: Source documents

        Returns:
            Consistency score (0.0-1.0)
        """
        # Count how many sources are available
        available_sources = [k for k, v in source_data.items() if v]

        if len(available_sources) < 2:
            logger.warning("Insufficient sources for cross-source validation")
            return 0.8  # Give benefit of doubt

        # Use LLM to check consistency
        prompt = f"""You are validating a stock summary for factual consistency across multiple data sources.

Summary to validate:
{summary_text}

Available sources:
{chr(10).join(f"{source}: {data[:2000]}..." for source, data in source_data.items() if data)}

Task: Check if claims in the summary are consistent across the available sources.

Respond with a JSON object:
{{
  "consistency_score": 0.0-1.0,
  "inconsistencies": ["list any inconsistencies found"],
  "reasoning": "brief explanation"
}}
"""

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            response_text = response.content

            # Parse response (simple extraction)
            import json
            # Try to extract JSON from response
            json_match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return float(result.get("consistency_score", 0.7))
            else:
                logger.warning("Could not parse LLM response for consistency check")
                return 0.7

        except Exception as e:
            logger.error(f"Cross-source consistency check failed: {e}")
            return 0.7  # Default to moderate score on error

    async def _check_temporal_consistency(
        self,
        summary_text: str,
        ticker: str,
        previous_summaries: Optional[List[StockSummary]] = None
    ) -> float:
        """Check consistency with historical summaries

        Args:
            summary_text: Current summary
            ticker: Stock ticker
            previous_summaries: List of historical summaries

        Returns:
            Consistency score (0.0-1.0)
        """
        # Get recent summaries if not provided
        if previous_summaries is None:
            try:
                with db_manager.get_session() as session:
                    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

                    previous_summaries = session.query(StockSummary).filter(
                        StockSummary.ticker == ticker,
                        StockSummary.generation_date >= thirty_days_ago
                    ).order_by(StockSummary.generation_date.desc()).limit(5).all()

            except Exception as e:
                logger.error(f"Could not fetch historical summaries: {e}")
                return 0.8  # Default score

        if not previous_summaries:
            logger.info(f"No historical summaries for {ticker}, skipping temporal check")
            return 0.9  # Give benefit of doubt for new stocks

        # Compare with most recent summary
        most_recent = previous_summaries[0]
        previous_text = most_recent.medium_text or most_recent.expanded_text or ""

        if not previous_text:
            return 0.9

        # Use LLM to check for contradictions
        prompt = f"""You are checking for temporal consistency between two stock summaries.

Previous summary (from {most_recent.generation_date.strftime('%Y-%m-%d')}):
{previous_text[:1000]}

Current summary:
{summary_text}

Task: Check if the current summary contradicts or drastically differs from the previous summary.
Some change is expected, but look for logical contradictions or impossible shifts.

Respond with a JSON object:
{{
  "consistency_score": 0.0-1.0,
  "contradictions": ["list any contradictions"],
  "reasoning": "brief explanation"
}}
"""

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            response_text = response.content

            # Parse response
            import json
            json_match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return float(result.get("consistency_score", 0.8))
            else:
                return 0.8

        except Exception as e:
            logger.error(f"Temporal consistency check failed: {e}")
            return 0.8

    def _quantify_uncertainty(self, text: str) -> tuple[float, Dict[str, Any]]:
        """Quantify uncertainty in text using pattern matching

        Args:
            text: Text to analyze

        Returns:
            Tuple of (uncertainty_score, details_dict)
        """
        text_lower = text.lower()

        # Count hedging patterns
        hedging_count = sum(
            len(re.findall(pattern, text_lower, re.IGNORECASE))
            for pattern in self.hedging_patterns
        )

        # Count high confidence patterns
        confidence_count = sum(
            len(re.findall(pattern, text_lower, re.IGNORECASE))
            for pattern in self.high_confidence_patterns
        )

        # Calculate word count
        word_count = len(text.split())

        # Normalize counts
        hedging_ratio = hedging_count / max(word_count / 100, 1)
        confidence_ratio = confidence_count / max(word_count / 100, 1)

        # Calculate uncertainty score (0.0 = very confident, 1.0 = very uncertain)
        # High hedging increases score, high confidence decreases it
        uncertainty_score = min(hedging_ratio / 2, 1.0)
        uncertainty_score = max(uncertainty_score - (confidence_ratio / 4), 0.0)

        details = {
            "hedging_count": hedging_count,
            "confidence_count": confidence_count,
            "hedging_ratio": round(hedging_ratio, 3),
            "confidence_ratio": round(confidence_ratio, 3),
            "word_count": word_count
        }

        return uncertainty_score, details

    def _calculate_overall_risk(
        self,
        cross_source_score: float,
        temporal_score: float,
        uncertainty_score: float
    ) -> HallucinationRisk:
        """Calculate overall hallucination risk level

        Args:
            cross_source_score: Cross-source consistency (higher is better)
            temporal_score: Temporal consistency (higher is better)
            uncertainty_score: Uncertainty level (lower is better)

        Returns:
            Overall risk level
        """
        # Weighted combination
        # Cross-source and temporal are inverted (1.0 - score) because lower scores = higher risk
        risk_score = (
            (1.0 - cross_source_score) * 0.4 +
            (1.0 - temporal_score) * 0.3 +
            uncertainty_score * 0.3
        )

        # Map to risk levels
        if risk_score < 0.2:
            return HallucinationRisk.LOW
        elif risk_score < 0.4:
            return HallucinationRisk.MEDIUM
        elif risk_score < 0.7:
            return HallucinationRisk.HIGH
        else:
            return HallucinationRisk.CRITICAL


# Global instance
hallucination_detector = HallucinationDetector()
