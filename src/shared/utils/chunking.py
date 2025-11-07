from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from typing import List
import tiktoken
import logging

from src.config.settings import settings

logger = logging.getLogger(__name__)


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count tokens in text"""
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except Exception as e:
        logger.warning(f"Failed to count tokens with {model}, using fallback: {e}")
        # Fallback to approximate word count * 1.3
        return int(len(text.split()) * 1.3)


def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 100) -> List[str]:
    """Chunk text into overlapping segments

    Args:
        text: Text to chunk
        chunk_size: Maximum tokens per chunk
        chunk_overlap: Number of overlapping tokens between chunks

    Returns:
        List of text chunks
    """
    if not text or not text.strip():
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=count_tokens,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    chunks = splitter.split_text(text)
    logger.info(f"Created {len(chunks)} chunks from text ({len(text)} chars)")

    return chunks


async def generate_embeddings(texts: List[str], batch_size: int = 100) -> List[List[float]]:
    """Generate embeddings in batches using text-embedding-3-large (3072 dims)

    Args:
        texts: List of texts to embed
        batch_size: Maximum texts per API call

    Returns:
        List of embedding vectors (each 3072 dimensions)
    """
    if not texts:
        return []

    embeddings_model = OpenAIEmbeddings(
        model="text-embedding-3-large",
        openai_api_key=settings.openai_api_key
    )

    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        logger.info(f"Generating embeddings for batch {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}")

        batch_embeddings = await embeddings_model.aembed_documents(batch)
        all_embeddings.extend(batch_embeddings)

    logger.info(f"Generated {len(all_embeddings)} embeddings")
    return all_embeddings
