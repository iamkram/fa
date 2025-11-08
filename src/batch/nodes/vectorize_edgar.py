from langchain_core.runnables import RunnableConfig
from typing import Dict, Any, Union
import asyncio
import uuid
import logging

from src.batch.state import BatchGraphState, BatchGraphStatePhase2
from src.shared.utils.chunking import chunk_text, generate_embeddings
from src.shared.vector_store.pgvector_client import PgVectorClient

logger = logging.getLogger(__name__)


def vectorize_edgar_node(state: Union[BatchGraphState, BatchGraphStatePhase2], config: RunnableConfig) -> Dict[str, Any]:
    """Vectorize EDGAR filings and store in pgvector

    Args:
        state: Current batch graph state
        config: Runnable configuration

    Returns:
        Updated state dict with vector_ids
    """
    logger.info(f"[VECTORIZATION] Processing {len(state.edgar_filings)} filings for {state.ticker}")

    if not state.edgar_filings:
        logger.warning(f"No EDGAR filings to vectorize for {state.ticker}")
        return {"vector_ids": []}

    pgvector = None
    vector_ids = []

    try:
        pgvector = PgVectorClient()

        for filing in state.edgar_filings:
            logger.info(f"Chunking {filing.filing_type} filing...")

            # Chunk the filing text
            chunks = chunk_text(filing.full_text, chunk_size=1000, chunk_overlap=100)

            if not chunks:
                logger.warning(f"No chunks created for {filing.filing_type}")
                continue

            logger.info(f"Generating embeddings for {len(chunks)} chunks...")

            # Generate embeddings (3072 dimensions)
            embeddings = asyncio.run(generate_embeddings(chunks, batch_size=100))

            # Prepare vectors for bulk insert
            vectors = []
            for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                vector_id = str(uuid.uuid4())
                vectors.append({
                    'id': vector_id,
                    'embedding': embedding,
                    'text': chunk,
                    'metadata': {
                        'stock_id': state.stock_id,
                        'ticker': state.ticker,
                        'filing_type': filing.filing_type,
                        'accession_number': filing.accession_number,
                        'filing_date': filing.filing_date.isoformat(),
                        'chunk_index': idx
                    }
                })
                vector_ids.append(vector_id)

            # Bulk insert into edgar_filings namespace
            logger.info(f"Storing {len(vectors)} vectors in pgvector...")
            pgvector.bulk_insert('edgar_filings', vectors)

        logger.info(f"✅ Vectorized {len(vector_ids)} chunks for {state.ticker}")

        return {
            "vector_ids": vector_ids,  # Phase 1 compatibility
            "edgar_vector_ids": vector_ids  # Phase 2 compatibility
        }

    except Exception as e:
        logger.error(f"❌ Vectorization failed for {state.ticker}: {str(e)}")
        return {
            "vector_ids": [],
            "edgar_vector_ids": [],  # Phase 2 compatibility
            "error_messages": [f"EDGAR vectorization error: {str(e)}"]
        }

    finally:
        if pgvector:
            pgvector.close()
