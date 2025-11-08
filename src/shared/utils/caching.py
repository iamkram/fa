"""
Embedding Cache Manager

Manages embedding caching in Redis to avoid re-embedding unchanged content.
Uses content hashing (SHA-256) to detect changes and skip redundant embeddings.
"""

import redis
import hashlib
import logging
from typing import Optional
from datetime import timedelta

from src.config.settings import settings

logger = logging.getLogger(__name__)


class EmbeddingCacheManager:
    """Manage embedding cache in Redis to optimize batch processing"""

    def __init__(self):
        """Initialize cache manager with Redis connection"""
        self.redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        self.ttl = 604800  # 7 days in seconds

    def _cache_key(self, identifier: str, source_type: str) -> str:
        """Generate Redis key for cached content hash

        Args:
            identifier: Unique identifier (e.g., ticker, document ID)
            source_type: Source type (edgar, bluematrix, factset)

        Returns:
            Redis key string
        """
        return f"embedding_cache:{source_type}:{identifier}"

    def compute_hash(self, content: str) -> str:
        """Compute SHA-256 hash of content

        Args:
            content: Text content to hash

        Returns:
            Hex digest of SHA-256 hash
        """
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    async def get_cached_hash(
        self,
        identifier: str,
        source_type: str
    ) -> Optional[str]:
        """Get cached content hash for identifier

        Args:
            identifier: Unique identifier (e.g., ticker)
            source_type: Source type (edgar, bluematrix, factset)

        Returns:
            Cached hash string if exists, None otherwise
        """
        try:
            key = self._cache_key(identifier, source_type)
            cached = self.redis_client.get(key)

            if cached:
                logger.debug(f"Cache hit: {source_type}:{identifier}")
                return cached
            else:
                logger.debug(f"Cache miss: {source_type}:{identifier}")
                return None

        except Exception as e:
            logger.error(f"Redis get error for {identifier}: {e}")
            return None

    async def set_cached_hash(
        self,
        identifier: str,
        source_type: str,
        content_hash: str
    ):
        """Store content hash in cache

        Args:
            identifier: Unique identifier (e.g., ticker)
            source_type: Source type (edgar, bluematrix, factset)
            content_hash: SHA-256 hash of content
        """
        try:
            key = self._cache_key(identifier, source_type)
            self.redis_client.setex(key, self.ttl, content_hash)
            logger.debug(f"Cached hash for {source_type}:{identifier}")

        except Exception as e:
            logger.error(f"Redis set error for {identifier}: {e}")

    async def should_reembed(
        self,
        identifier: str,
        source_type: str,
        current_content: str
    ) -> bool:
        """Check if content should be re-embedded

        Compares current content hash with cached hash.

        Args:
            identifier: Unique identifier (e.g., ticker)
            source_type: Source type (edgar, bluematrix, factset)
            current_content: Current content text

        Returns:
            True if content changed (or no cache), False if unchanged
        """
        current_hash = self.compute_hash(current_content)
        cached_hash = await self.get_cached_hash(identifier, source_type)

        if cached_hash is None:
            # No cache entry, need to embed
            logger.info(f"No cache for {source_type}:{identifier}, will embed")
            return True

        if current_hash != cached_hash:
            # Content changed, need to re-embed
            logger.info(f"Content changed for {source_type}:{identifier}, will re-embed")
            return True

        # Content unchanged, skip embedding
        logger.info(f"Content unchanged for {source_type}:{identifier}, skipping embed")
        return False

    async def invalidate(self, identifier: str, source_type: str):
        """Invalidate cache entry

        Args:
            identifier: Unique identifier
            source_type: Source type
        """
        try:
            key = self._cache_key(identifier, source_type)
            self.redis_client.delete(key)
            logger.info(f"Invalidated cache for {source_type}:{identifier}")

        except Exception as e:
            logger.error(f"Redis delete error for {identifier}: {e}")

    async def get_cache_stats(self) -> dict:
        """Get cache statistics

        Returns:
            Dict with cache statistics
        """
        try:
            # Count cache keys
            pattern = "embedding_cache:*"
            keys = self.redis_client.keys(pattern)

            # Group by source type
            stats = {
                "total_entries": len(keys),
                "by_source": {}
            }

            for key in keys:
                parts = key.split(":")
                if len(parts) >= 2:
                    source = parts[1]
                    stats["by_source"][source] = stats["by_source"].get(source, 0) + 1

            return stats

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"error": str(e)}


# Global instance
embedding_cache_manager = EmbeddingCacheManager()
