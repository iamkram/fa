from src.shared.vector_store.pgvector_client import PgVectorClient
from langchain_openai import OpenAIEmbeddings
from langchain_anthropic import ChatAnthropic
from typing import List, Dict, Any, Optional
import logging
import asyncio

from src.config.settings import settings

logger = logging.getLogger(__name__)


async def hybrid_search(
    query: str,
    namespaces: List[str],
    stock_id: str,
    top_k: int = 10,
    threshold: float = 0.75
) -> List[Dict[str, Any]]:
    """Hybrid dense + sparse search across multiple namespaces

    Args:
        query: Search query text
        namespaces: List of vector store namespaces to search
        stock_id: Filter results to this stock ID
        top_k: Maximum results to return
        threshold: Minimum similarity score (0-1)

    Returns:
        List of search results with text, metadata, and similarity scores
    """
    try:
        # Generate query embedding using text-embedding-3-large (3072 dims)
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-large",
            openai_api_key=settings.openai_api_key
        )
        query_embedding = await embeddings.aembed_query(query)

        # Dense search via pgvector
        pgvector = PgVectorClient()
        all_results = []

        for namespace in namespaces:
            try:
                results = pgvector.similarity_search(
                    namespace=namespace,
                    query_embedding=query_embedding,
                    top_k=top_k,
                    threshold=threshold,
                    filter_metadata={"stock_id": stock_id}
                )
                all_results.extend(results)
                logger.info(f"Found {len(results)} results in {namespace}")
            except Exception as e:
                logger.warning(f"Search failed for namespace {namespace}: {e}")
                continue

        pgvector.close()

        # Sort by similarity score (highest first)
        all_results.sort(key=lambda x: x.get('similarity', 0), reverse=True)

        # Return top K results
        top_results = all_results[:top_k]
        logger.info(f"Returning {len(top_results)} total results")

        return top_results

    except Exception as e:
        logger.error(f"Hybrid search failed: {e}")
        return []


async def rerank_results(
    query: str,
    results: List[Dict[str, Any]],
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """LLM-based reranking for better relevance

    Uses Claude to evaluate query-document relevance beyond vector similarity.
    Particularly useful for complex financial queries requiring semantic understanding.

    Args:
        query: User query
        results: List of vector search results
        top_k: Number of top results to return after reranking

    Returns:
        Reranked list of results with relevance scores
    """
    if not results or len(results) <= 1:
        return results

    try:
        llm = ChatAnthropic(
            model="claude-haiku-4-20250508",  # Fast model for reranking
            temperature=0,
            max_tokens=2000,
            anthropic_api_key=settings.anthropic_api_key
        )

        # Build reranking prompt
        docs_text = "\n\n".join([
            f"Document {i+1}:\n{r.get('text', '')[:500]}"  # Limit to 500 chars per doc
            for i, r in enumerate(results)
        ])

        prompt = f"""Given the query and documents below, rank the documents by relevance to the query.
Output ONLY a JSON array of document numbers in order of relevance (most relevant first).
Example: [3, 1, 5, 2, 4]

Query: {query}

Documents:
{docs_text}

Ranking (JSON array only):"""

        response = await llm.ainvoke(prompt)
        content = response.content.strip()

        # Parse ranking
        import json
        import re
        # Extract JSON array from response
        match = re.search(r'\[[\d,\s]+\]', content)
        if match:
            ranking = json.loads(match.group())

            # Reorder results based on ranking
            reranked = []
            for rank_idx in ranking[:top_k]:
                if 1 <= rank_idx <= len(results):
                    result = results[rank_idx - 1].copy()
                    result['rerank_score'] = 1.0 - (len(reranked) / top_k)  # Higher is better
                    reranked.append(result)

            logger.info(f"Reranked {len(results)} \u2192 {len(reranked)} results")
            return reranked
        else:
            logger.warning("Failed to parse reranking response, returning original order")
            return results[:top_k]

    except Exception as e:
        logger.error(f"Reranking failed: {e}, returning original order")
        return results[:top_k]


def extract_citations(results: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Extract structured citations from search results

    Creates citation metadata for transparency and fact-checking.
    Citations include source type, date, and relevance score.

    Args:
        results: List of search results with metadata

    Returns:
        List of citation dictionaries
    """
    citations = []

    for i, result in enumerate(results):
        metadata = result.get('metadata', {})

        citation = {
            'citation_id': f"cite_{i+1}",
            'source_type': metadata.get('source', 'unknown'),
            'text_snippet': result.get('text', '')[:200] + "...",  # First 200 chars
            'similarity_score': result.get('similarity', 0.0),
            'rerank_score': result.get('rerank_score'),
        }

        # Add source-specific metadata
        if metadata.get('source') == 'edgar':
            citation['filing_type'] = metadata.get('filing_type')
            citation['filing_date'] = metadata.get('filing_date')
            citation['accession_number'] = metadata.get('accession_number')
        elif metadata.get('source') == 'bluematrix':
            citation['analyst_firm'] = metadata.get('analyst_firm')
            citation['report_date'] = metadata.get('report_date')
            citation['rating'] = metadata.get('new_rating')
        elif metadata.get('source') == 'factset':
            citation['data_type'] = metadata.get('data_type')
            citation['date'] = metadata.get('date')

        citations.append(citation)

    return citations


async def enhanced_rag_retrieve(
    query: str,
    stock_id: str,
    namespaces: Optional[List[str]] = None,
    top_k: int = 10,
    rerank: bool = True
) -> Dict[str, Any]:
    """Enhanced RAG retrieval with reranking and citation tracking

    Complete RAG pipeline:
    1. Multi-source vector search
    2. LLM-based reranking for relevance
    3. Citation extraction for transparency

    Args:
        query: User query
        stock_id: Filter to specific stock
        namespaces: List of namespaces to search (default: all 3 sources)
        top_k: Number of results to return
        rerank: Whether to apply LLM reranking

    Returns:
        Dict with results, citations, and metadata
    """
    if namespaces is None:
        namespaces = ['edgar_filings', 'bluematrix_reports', 'factset_data']

    # Step 1: Vector search
    results = await hybrid_search(
        query=query,
        namespaces=namespaces,
        stock_id=stock_id,
        top_k=top_k * 2 if rerank else top_k,  # Get more for reranking
        threshold=0.7
    )

    if not results:
        logger.warning(f"No results found for query: {query}")
        return {
            'results': [],
            'citations': [],
            'metadata': {
                'total_results': 0,
                'reranked': False,
                'namespaces_searched': namespaces
            }
        }

    # Step 2: Rerank if enabled
    if rerank and len(results) > 1:
        results = await rerank_results(query, results, top_k=top_k)
        reranked = True
    else:
        results = results[:top_k]
        reranked = False

    # Step 3: Extract citations
    citations = extract_citations(results)

    logger.info(
        f"Enhanced RAG: {len(results)} results, "
        f"reranked={reranked}, citations={len(citations)}"
    )

    return {
        'results': results,
        'citations': citations,
        'metadata': {
            'total_results': len(results),
            'reranked': reranked,
            'namespaces_searched': namespaces,
            'query': query
        }
    }
