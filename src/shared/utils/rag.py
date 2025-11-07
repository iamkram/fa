from src.shared.vector_store.pgvector_client import PgVectorClient
from langchain_openai import OpenAIEmbeddings
from typing import List, Dict, Any
import logging

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
