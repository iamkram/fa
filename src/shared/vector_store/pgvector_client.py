from typing import List, Dict, Any, Optional
import numpy as np
from pgvector.psycopg2 import register_vector
import psycopg2
from psycopg2.extras import execute_values, Json
import logging
import json

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

class PgVectorClient:
    """Client for pgvector with namespace support"""

    def __init__(self):
        self.settings = get_settings()
        self.conn = None
        self._connect()

    def _connect(self):
        """Establish connection to PostgreSQL"""
        try:
            self.conn = psycopg2.connect(self.settings.database_url)
            self._initialize_extension()
            register_vector(self.conn)
            logger.info("Connected to pgvector")
        except Exception as e:
            logger.error(f"Failed to connect to pgvector: {str(e)}")
            raise

    def _initialize_extension(self):
        """Enable pgvector extension"""
        with self.conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            self.conn.commit()

    def create_collection(self, namespace: str, dimension: int = 1536):
        """Create a collection (table) for a namespace

        Note: pgvector indexes (HNSW/IVFFlat) support max 2000 dimensions.
        For larger dimensions, tables are created without indexes (slower search).
        Consider using text-embedding-3-small (1536 dims) instead of 3-large (3072 dims).
        """
        table_name = f"vectors_{namespace}"
        with self.conn.cursor() as cur:
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id UUID PRIMARY KEY,
                    embedding vector({dimension}),
                    metadata JSONB,
                    text TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # pgvector indexes support max 2000 dimensions
            if dimension <= 2000:
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS {table_name}_embedding_idx
                    ON {table_name}
                    USING hnsw (embedding vector_cosine_ops)
                """)
                logger.info(f"Created collection: {namespace} with HNSW index")
            else:
                logger.warning(f"Created collection: {namespace} WITHOUT index (dimension {dimension} > 2000)")
                logger.warning(f"Consider using smaller embedding dimensions for better performance")
            self.conn.commit()

    def insert(
        self,
        namespace: str,
        id: str,
        embedding: List[float],
        text: str,
        metadata: Dict[str, Any]
    ):
        """Insert a vector into a namespace"""
        table_name = f"vectors_{namespace}"
        with self.conn.cursor() as cur:
            cur.execute(f"""
                INSERT INTO {table_name} (id, embedding, text, metadata)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                SET embedding = EXCLUDED.embedding,
                    text = EXCLUDED.text,
                    metadata = EXCLUDED.metadata
            """, (id, np.array(embedding), text, Json(metadata)))
            self.conn.commit()

    def bulk_insert(
        self,
        namespace: str,
        vectors: List[Dict[str, Any]]
    ):
        """Bulk insert vectors"""
        table_name = f"vectors_{namespace}"
        values = [
            (v['id'], np.array(v['embedding']), v['text'], Json(v['metadata']))
            for v in vectors
        ]
        with self.conn.cursor() as cur:
            execute_values(
                cur,
                f"""
                INSERT INTO {table_name} (id, embedding, text, metadata)
                VALUES %s
                ON CONFLICT (id) DO UPDATE
                SET embedding = EXCLUDED.embedding,
                    text = EXCLUDED.text,
                    metadata = EXCLUDED.metadata
                """,
                values
            )
            self.conn.commit()
            logger.info(f"Bulk inserted {len(vectors)} vectors into {namespace}")

    def similarity_search(
        self,
        namespace: str,
        query_embedding: List[float],
        top_k: int = 10,
        threshold: float = 0.75,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar vectors using cosine similarity"""
        table_name = f"vectors_{namespace}"

        query = f"""
            SELECT id, text, metadata,
                   1 - (embedding <=> %s::vector) as similarity
            FROM {table_name}
            WHERE 1 - (embedding <=> %s::vector) > %s
        """

        params = [np.array(query_embedding), np.array(query_embedding), threshold]

        if filter_metadata:
            for key, value in filter_metadata.items():
                query += f" AND metadata->>'{key}' = %s"
                params.append(str(value))

        query += " ORDER BY embedding <=> %s::vector LIMIT %s"
        params.extend([np.array(query_embedding), top_k])

        with self.conn.cursor() as cur:
            cur.execute(query, params)
            results = cur.fetchall()

        return [
            {
                'id': row[0],
                'text': row[1],
                'metadata': row[2],
                'similarity': float(row[3])
            }
            for row in results
        ]

    def close(self):
        """Close connection"""
        if self.conn:
            self.conn.close()
            logger.info("Closed pgvector connection")
