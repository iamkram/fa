import asyncio
import uuid
import logging
from typing import Dict, Any

from src.batch.state import BatchGraphStatePhase2
from src.shared.utils.chunking import generate_embeddings
from src.shared.vector_store.pgvector_client import PgVectorClient

logger = logging.getLogger(__name__)


def vectorize_factset_node(state: BatchGraphStatePhase2, config) -> Dict[str, Any]:
    """Vectorize FactSet data (convert metrics to natural language first)"""
    logger.info(f"[FactSet Vectorization] Processing data for {state.ticker}")

    if not state.factset_price_data:
        logger.info(f"No FactSet data to vectorize for {state.ticker}")
        return {"factset_vector_ids": []}

    pgvector = PgVectorClient()
    vector_ids = []

    try:
        # Convert price data to natural language
        price_text = f"""
{state.ticker} price movement on {state.factset_price_data.date.strftime('%Y-%m-%d')}:
- Opened at ${state.factset_price_data.open}, closed at ${state.factset_price_data.close}
- Daily change: {state.factset_price_data.pct_change}%
- Volume: {state.factset_price_data.volume:,} shares ({state.factset_price_data.volume_vs_avg}x average)
- High: ${state.factset_price_data.high}, Low: ${state.factset_price_data.low}
- Volatility ranking: {state.factset_price_data.volatility_percentile * 100:.0f}th percentile
        """.strip()

        texts = [price_text]

        # Add fundamental events
        for event in state.factset_events:
            event_text = f"{event.event_type.upper()} on {event.timestamp.strftime('%Y-%m-%d')}: {event.details}"
            texts.append(event_text)

        logger.info(f"Generating embeddings for {len(texts)} FactSet items...")

        # Generate embeddings
        embeddings = asyncio.run(generate_embeddings(texts))

        # Store vectors
        vectors = []
        for idx, (text, embedding) in enumerate(zip(texts, embeddings)):
            vector_id = str(uuid.uuid4())

            metadata = {
                'stock_id': state.stock_id,
                'ticker': state.ticker,
                'source': 'factset',
                'data_type': 'price' if idx == 0 else 'event',
                'date': state.factset_price_data.date.isoformat()
            }

            if idx > 0:  # Event
                metadata['event_type'] = state.factset_events[idx-1].event_type

            vectors.append({
                'id': vector_id,
                'embedding': embedding,
                'text': text,
                'metadata': metadata
            })
            vector_ids.append(vector_id)

        pgvector.bulk_insert('factset_data', vectors)

        logger.info(f"✅ Vectorized {len(vector_ids)} FactSet items for {state.ticker}")

        return {"factset_vector_ids": vector_ids}

    except Exception as e:
        logger.error(f"❌ FactSet vectorization failed: {str(e)}")
        return {"factset_vector_ids": [], "error_message": str(e)}
    finally:
        pgvector.close()
