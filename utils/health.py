"""
Health check utilities for Redis and Celery.
"""
import redis
import logging
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


def check_redis_connection(timeout: int = 5) -> dict:
    """
    Check Redis connection status.
    
    Returns:
        dict with 'healthy', 'message', and 'latency_ms' keys
    """
    if not getattr(settings, 'REDIS_URL', None):
        return {
            'healthy': False,
            'message': 'Redis URL not configured',
            'latency_ms': None
        }
    
    import time
    start = time.time()
    
    try:
        r = redis.from_url(settings.REDIS_URL, socket_timeout=timeout)
        result = r.ping()
        latency = (time.time() - start) * 1000
        
        if result:
            return {
                'healthy': True,
                'message': 'Connected',
                'latency_ms': round(latency, 2)
            }
        else:
            return {
                'healthy': False,
                'message': 'Ping failed',
                'latency_ms': round(latency, 2)
            }
    except redis.exceptions.TimeoutError:
        return {
            'healthy': False,
            'message': 'Connection timeout',
            'latency_ms': timeout * 1000
        }
    except redis.exceptions.ConnectionError as e:
        return {
            'healthy': False,
            'message': f'Connection error: {str(e)[:100]}',
            'latency_ms': None
        }
    except Exception as e:
        return {
            'healthy': False,
            'message': f'Error: {str(e)[:100]}',
            'latency_ms': None
        }


def check_cache_connection() -> dict:
    """
    Check Django cache backend status.
    
    Returns:
        dict with 'healthy', 'message', and 'backend' keys
    """
    backend = settings.CACHES.get('default', {}).get('BACKEND', 'unknown')
    backend_name = backend.split('.')[-1]
    
    try:
        # Try to set and get a test value
        test_key = '_health_check_test'
        test_value = 'ok'
        
        cache.set(test_key, test_value, timeout=10)
        result = cache.get(test_key)
        cache.delete(test_key)
        
        if result == test_value:
            return {
                'healthy': True,
                'message': 'Cache operational',
                'backend': backend_name
            }
        else:
            return {
                'healthy': False,
                'message': 'Cache read/write mismatch',
                'backend': backend_name
            }
    except Exception as e:
        return {
            'healthy': False,
            'message': f'Cache error: {str(e)[:100]}',
            'backend': backend_name
        }


def check_celery_status() -> dict:
    """
    Check if Celery worker is responsive.
    
    Returns:
        dict with 'healthy', 'message', and 'workers' keys
    """
    try:
        from base.celery import app
        
        # Ping workers with short timeout
        inspector = app.control.inspect(timeout=2.0)
        active = inspector.active()
        
        if active:
            worker_count = len(active)
            return {
                'healthy': True,
                'message': f'{worker_count} worker(s) active',
                'workers': list(active.keys())
            }
        else:
            return {
                'healthy': False,
                'message': 'No workers responding',
                'workers': []
            }
    except Exception as e:
        return {
            'healthy': False,
            'message': f'Cannot connect to broker: {str(e)[:100]}',
            'workers': []
        }


def get_full_health_status() -> dict:
    """
    Get complete health status of all services.
    
    Returns:
        dict with status of redis, cache, celery, and overall health
    """
    redis_status = check_redis_connection()
    cache_status = check_cache_connection()
    celery_status = check_celery_status()
    
    # Overall health: True if at least cache works (allows sync fallback)
    overall_healthy = cache_status['healthy']
    
    return {
        'healthy': overall_healthy,
        'services': {
            'redis': redis_status,
            'cache': cache_status,
            'celery': celery_status
        },
        'mode': {
            'async_enabled': getattr(settings, 'ELASTICITY_ASYNC_ENABLED', False),
            'redis_cache_enabled': getattr(settings, 'REDIS_CACHE_ENABLED', False)
        }
    }
