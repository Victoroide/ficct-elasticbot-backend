"""
Redis caching for AI interpretations to reduce AWS costs.
"""
import hashlib
import json
from typing import Optional
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


class InterpretationCache:
    """
    Manages caching of AI-generated interpretations.

    Cache key: hash of (elasticity, classification, context)
    TTL: 24 hours (86400 seconds)
    """

    CACHE_PREFIX = 'ai_interpretation'
    CACHE_TTL = 86400  # 24 hours

    @classmethod
    def get_cache_key(cls, elasticity: float, classification: str, context: dict) -> str:
        """
        Generate cache key from calculation parameters.

        Uses MD5 hash of JSON representation for consistent keys.
        """
        cache_data = {
            'elasticity': round(elasticity, 4),
            'classification': classification,
            'method': context.get('method', ''),
            'data_points': context.get('data_points', 0)
        }

        cache_string = json.dumps(cache_data, sort_keys=True)
        hash_digest = hashlib.md5(cache_string.encode()).hexdigest()

        return f"{cls.CACHE_PREFIX}:{hash_digest}"

    @classmethod
    def get(cls, elasticity: float, classification: str, context: dict) -> Optional[str]:
        """
        Retrieve cached interpretation if exists.

        Returns:
            Cached interpretation text or None if not cached or cache unavailable
        """
        try:
            cache_key = cls.get_cache_key(elasticity, classification, context)
            interpretation = cache.get(cache_key)

            if interpretation:
                logger.info(f"Cache HIT for interpretation: {cache_key}")
            else:
                logger.debug(f"Cache MISS for interpretation: {cache_key}")

            return interpretation
        except Exception as e:
            # Cache unavailable - continue without cache
            logger.warning(f"Cache GET failed, continuing without cache: {e}")
            return None

    @classmethod
    def set(
        cls,
        elasticity: float,
        classification: str,
        context: dict,
        interpretation: str
    ) -> None:
        """
        Cache interpretation with 24h TTL.
        Fails silently if cache is unavailable.
        """
        try:
            cache_key = cls.get_cache_key(elasticity, classification, context)
            cache.set(cache_key, interpretation, cls.CACHE_TTL)
            logger.info(f"Cached interpretation: {cache_key} (TTL: {cls.CACHE_TTL}s)")
        except Exception as e:
            # Cache unavailable - continue without caching
            logger.warning(f"Cache SET failed, interpretation not cached: {e}")

    @classmethod
    def invalidate(cls, elasticity: float, classification: str, context: dict) -> None:
        """
        Manually invalidate cached interpretation.
        Fails silently if cache is unavailable.
        """
        try:
            cache_key = cls.get_cache_key(elasticity, classification, context)
            cache.delete(cache_key)
            logger.info(f"Invalidated cache: {cache_key}")
        except Exception as e:
            logger.warning(f"Cache DELETE failed: {e}")
