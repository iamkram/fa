import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np

from src.shared.vector_store.pgvector_client import PgVectorClient

@pytest.fixture
def mock_pgvector():
    """Mock pgvector client"""
    with patch('src.shared.vector_store.pgvector_client.psycopg2.connect') as mock_connect, \
         patch('src.shared.vector_store.pgvector_client.register_vector'):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        # Set up cursor context manager
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_conn.cursor.return_value.__exit__.return_value = False
        mock_connect.return_value = mock_conn

        client = PgVectorClient()
        client.conn = mock_conn
        yield client, mock_cursor

def test_create_collection(mock_pgvector):
    """Test creating a vector collection"""
    client, mock_cursor = mock_pgvector

    client.create_collection("test_namespace", dimension=1536)

    # Verify table creation SQL was called (check all calls, not just first)
    assert mock_cursor.execute.called
    all_calls = str(mock_cursor.execute.call_args_list)
    assert "CREATE TABLE" in all_calls
    assert "vectors_test_namespace" in all_calls

def test_insert_vector(mock_pgvector):
    """Test inserting a vector"""
    client, mock_cursor = mock_pgvector

    client.insert(
        namespace="test",
        id="test-id",
        embedding=[0.1] * 1536,
        text="Test text",
        metadata={"source": "test"}
    )

    assert mock_cursor.execute.called
