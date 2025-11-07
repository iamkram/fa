#!/usr/bin/env python3
"""Setup database tables and pgvector collections"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.shared.database.connection import db_manager
from src.shared.vector_store.pgvector_client import PgVectorClient
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup():
    """Initialize database and vector collections"""
    try:
        # Create relational tables
        logger.info("Creating database tables...")
        db_manager.create_tables()

        # Create vector collections
        logger.info("Creating vector collections...")
        pgvector = PgVectorClient()

        namespaces = ["bluematrix_reports", "edgar_filings", "factset_data"]
        for namespace in namespaces:
            # Using 3072 dimensions (OpenAI text-embedding-3-large)
            # Note: No HNSW index for dimensions > 2000, but full table scan is acceptable for MVP
            pgvector.create_collection(namespace, dimension=3072)

        pgvector.close()

        logger.info("✅ Database setup complete!")

    except Exception as e:
        logger.error(f"❌ Setup failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    setup()
