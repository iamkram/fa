import asyncio
import uuid
import logging
from typing import Dict, Any

from src.batch.state import BatchGraphStatePhase2
from src.shared.utils.chunking import chunk_text, generate_embeddings
from src.shared.vector_store.pgvector_client import PgVectorClient

logger = logging.getLogger(__name__)


def vectorize_bluematrix_node(state: BatchGraphStatePhase2, config) -> Dict[str, Any]:
    """Vectorize BlueMatrix reports and store in pgvector"""
    logger.info(f"[BlueMatrix Vectorization] Processing reports for {state.ticker}")

    if not state.bluematrix_reports:
        logger.info(f"No BlueMatrix reports to vectorize for {state.ticker}")
        return {"bluematrix_vector_ids": []}

    pgvector = PgVectorClient()
    vector_ids = []

    try:
        for report in state.bluematrix_reports:
            # Chunk the report text
            logger.info(f"Chunking BlueMatrix report {report.report_id}...")
            chunks = chunk_text(report.full_text, chunk_size=500, chunk_overlap=50)

            # Generate embeddings
            logger.info(f"Generating embeddings for {len(chunks)} chunks...")
            embeddings = asyncio.run(generate_embeddings(chunks))

            # Prepare vectors with metadata
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
                        'source': 'bluematrix',
                        'report_id': report.report_id,
                        'analyst_firm': report.analyst_firm,
                        'analyst_name': report.analyst_name,
                        'report_date': report.report_date.isoformat(),
                        'rating_change': report.rating_change,
                        'new_rating': report.new_rating,
                        'price_target': report.price_target,
                        'chunk_index': idx
                    }
                })
                vector_ids.append(vector_id)

            # Bulk insert into bluematrix_reports namespace
            pgvector.bulk_insert('bluematrix_reports', vectors)
            logger.info(f"✅ Stored {len(vectors)} vectors for report {report.report_id}")

        logger.info(f"✅ Vectorized {len(vector_ids)} total chunks for {state.ticker}")

        return {"bluematrix_vector_ids": vector_ids}

    except Exception as e:
        logger.error(f"❌ BlueMatrix vectorization failed: {str(e)}")
        return {
            "bluematrix_vector_ids": [],
            "error_messages": [f"BlueMatrix vectorization error: {str(e)}"]
        }
    finally:
        pgvector.close()
