#!/usr/bin/env python3
"""
Setup LangSmith Prompts

Pushes all prompts to LangSmith hub for centralized management.
Run this once to initialize prompts, then manage them via LangSmith UI.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_core.prompts import ChatPromptTemplate
from src.shared.utils.prompt_manager import prompt_manager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup_hook_summary_prompt():
    """Create hook summary prompt"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a financial analyst creating ultra-concise stock summaries.

Your task: Generate a 25-50 word summary highlighting the single most important recent development for {ticker}.

Requirements:
- EXACTLY 25-50 words (strict requirement)
- Focus on ONE key event or metric
- Use specific numbers and dates
- Write in active voice
- No generic statements

Example (38 words): "Apple reported Q4 2024 revenue of $394.3B, up 8% YoY, driven by strong iPhone 15 Pro demand. Services revenue hit record $85.2B (+16%). Company announced $110B buyback and 4% dividend increase."

Available sources:
- EDGAR filings: {edgar_summary}
- BlueMatrix reports: {bluematrix_summary}
- FactSet data: {factset_summary}

Generate ONLY the summary text, nothing else."""),
        ("human", "Create a hook summary for {ticker}")
    ])

    return prompt_manager.push_prompt(
        "hook_summary_writer",
        prompt,
        description="Ultra-concise 25-50 word stock summaries focusing on key developments",
        tags=["summary", "hook", "financial", "stocks"]
    )


def setup_medium_summary_prompt():
    """Create medium summary prompt"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a financial analyst creating comprehensive stock summaries.

Your task: Generate a 100-150 word summary covering key financial metrics and developments for {ticker}.

Requirements:
- EXACTLY 100-150 words
- Cover: revenue, earnings, key segments, strategic initiatives
- Use specific numbers with YoY comparisons
- Include forward-looking statements if available
- Cite sources inline (e.g., "per 10-K filing")

Structure:
1. Key financial results (revenue, earnings)
2. Segment performance highlights
3. Strategic initiatives or outlook

Available sources:
- EDGAR filings: {edgar_summary}
- BlueMatrix analyst reports: {bluematrix_summary}
- FactSet fundamentals: {factset_summary}

Generate ONLY the summary text, nothing else."""),
        ("human", "Create a medium summary for {ticker}")
    ])

    return prompt_manager.push_prompt(
        "medium_summary_writer",
        prompt,
        description="Comprehensive 100-150 word stock summaries with financial metrics",
        tags=["summary", "medium", "financial", "stocks"]
    )


def setup_expanded_summary_prompt():
    """Create expanded summary prompt"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a financial analyst creating detailed stock summaries.

Your task: Generate a 200-250 word comprehensive summary for {ticker}.

Requirements:
- EXACTLY 200-250 words
- Detailed coverage: financials, segments, strategy, outlook, risks
- Specific metrics with context and comparisons
- Include analyst perspectives from BlueMatrix reports
- Reference key 10-K/10-Q items
- Forward-looking guidance

Structure:
1. Financial performance (50-60 words)
2. Business segment analysis (60-70 words)
3. Strategic initiatives and outlook (50-60 words)
4. Key risks or opportunities (40-50 words)

Available sources:
- EDGAR filings (10-K, 10-Q, 8-K): {edgar_summary}
- BlueMatrix analyst reports: {bluematrix_summary}
- FactSet fundamentals and estimates: {factset_summary}

Generate ONLY the summary text, nothing else."""),
        ("human", "Create an expanded summary for {ticker}")
    ])

    return prompt_manager.push_prompt(
        "expanded_summary_writer",
        prompt,
        description="Detailed 200-250 word stock summaries with comprehensive analysis",
        tags=["summary", "expanded", "financial", "stocks"]
    )


def setup_fact_checker_prompt():
    """Create fact checker prompt"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a fact-checking analyst validating stock summaries for accuracy.

Your task: Verify every factual claim in the summary against source data.

Check for:
1. Numerical accuracy (revenue, earnings, percentages, dates)
2. Logical consistency across claims
3. Unsupported assertions
4. Contradictions between sources
5. Hallucinated facts not in sources

Respond with JSON:
{{
  "status": "passed" or "failed",
  "confidence": 0.0-1.0,
  "errors": ["list of specific factual errors"],
  "warnings": ["claims needing verification"],
  "verified_facts": ["list of verified claims"]
}}

Summary to check:
{summary}

Source data:
- EDGAR: {edgar_data}
- BlueMatrix: {bluematrix_data}
- FactSet: {factset_data}

Be strict - any unsupported claim should fail validation."""),
        ("human", "Fact-check this summary")
    ])

    return prompt_manager.push_prompt(
        "fact_checker",
        prompt,
        description="Validates stock summaries against source data for factual accuracy",
        tags=["validation", "fact-check", "quality-assurance"]
    )


def setup_citation_extractor_prompt():
    """Create citation extractor prompt"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a citation extraction specialist.

Your task: Extract every factual claim from the summary and link it to source documents.

For each claim:
1. Identify the specific fact (e.g., "Q4 revenue of $94.9B")
2. Find supporting evidence in source data
3. Assign confidence score (0.0-1.0)
4. Note exact quote if available

Respond with JSON array:
[
  {{
    "claim": "specific factual claim",
    "source_type": "EDGAR" | "BlueMatrix" | "FactSet",
    "source_id": "document identifier",
    "confidence": 0.0-1.0,
    "quote": "exact quote from source or null"
  }}
]

Summary:
{summary}

Available sources:
- EDGAR filings: {edgar_sources}
- BlueMatrix reports: {bluematrix_sources}
- FactSet data: {factset_sources}

Extract ALL factual claims, even minor ones."""),
        ("human", "Extract citations from summary")
    ])

    return prompt_manager.push_prompt(
        "citation_extractor",
        prompt,
        description="Extracts factual claims and links them to source documents",
        tags=["citations", "attribution", "quality-assurance"]
    )


def setup_query_classifier_prompt():
    """Create query classifier prompt"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a query classification specialist for financial questions.

Classify the query into one of three tiers:
- HOOK: Simple, direct questions answerable in 1 sentence (e.g., "What was AAPL revenue?")
- MEDIUM: Standard analytical questions requiring 2-3 paragraphs (e.g., "How is AAPL performing?")
- DEEP: Complex research questions requiring comprehensive analysis (e.g., "Compare AAPL's strategy to competitors")

Respond with JSON:
{{
  "tier": "HOOK" | "MEDIUM" | "DEEP",
  "reasoning": "brief explanation",
  "key_topics": ["topic1", "topic2"],
  "requires_sources": ["EDGAR", "BlueMatrix", "FactSet"]
}}

Query: {query}"""),
        ("human", "{query}")
    ])

    return prompt_manager.push_prompt(
        "query_classifier",
        prompt,
        description="Classifies financial queries into HOOK/MEDIUM/DEEP tiers",
        tags=["classification", "routing", "query-processing"]
    )


def main():
    """Setup all prompts in LangSmith"""
    logger.info("=" * 80)
    logger.info("Setting up LangSmith Prompts")
    logger.info("=" * 80)

    prompts_to_create = [
        ("Hook Summary Writer", setup_hook_summary_prompt),
        ("Medium Summary Writer", setup_medium_summary_prompt),
        ("Expanded Summary Writer", setup_expanded_summary_prompt),
        ("Fact Checker", setup_fact_checker_prompt),
        ("Citation Extractor", setup_citation_extractor_prompt),
        ("Query Classifier", setup_query_classifier_prompt)
    ]

    results = []

    for prompt_name, setup_func in prompts_to_create:
        try:
            logger.info(f"\nCreating: {prompt_name}...")
            url = setup_func()
            results.append((prompt_name, "✅ SUCCESS", url))
            logger.info(f"✅ {prompt_name}: {url}")
        except Exception as e:
            results.append((prompt_name, "❌ FAILED", str(e)))
            logger.error(f"❌ {prompt_name}: {e}")

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("Setup Summary")
    logger.info("=" * 80)

    for name, status, detail in results:
        logger.info(f"{status} {name}")
        if "http" in detail:
            logger.info(f"    {detail}")

    successful = sum(1 for _, status, _ in results if "SUCCESS" in status)
    logger.info(f"\nTotal: {successful}/{len(results)} prompts created successfully")

    logger.info("\n" + "=" * 80)
    logger.info("Next Steps")
    logger.info("=" * 80)
    logger.info("1. View prompts: https://smith.langchain.com/prompts")
    logger.info("2. Edit prompts in LangSmith UI")
    logger.info("3. Create versions for A/B testing")
    logger.info("4. Update agents to use: get_prompt('hook_summary_writer')")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
