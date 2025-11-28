"""
IP-based rate limiting decorators for anonymous API access.

No authentication required - rate limits based on client IP address.
Rate limiting can be disabled globally via RATE_LIMITING_ENABLED=False in .env
"""
from functools import wraps
from django.core.cache import cache
from rest_framework.response import Response
from rest_framework import status
import os
import logging

logger = logging.getLogger(__name__)


def is_rate_limiting_enabled() -> bool:
    """Check if rate limiting is enabled via environment variable."""
    return os.environ.get('RATE_LIMITING_ENABLED', 'True').lower() in ('true', '1', 'yes')


def get_client_ip(request) -> str:
    """
    Extract client IP address from request.

    Handles X-Forwarded-For header for proxied requests.

    Args:
        request: Django HttpRequest object

    Returns:
        Client IP address as string
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
    return ip


def anonymous_rate_limit(max_requests: int, window_seconds: int):
    """
    Rate limit decorator using client IP address (no authentication required).

    Args:
        max_requests: Maximum requests allowed in time window
        window_seconds: Time window in seconds

    Usage:
        @anonymous_rate_limit(max_requests=10, window_seconds=3600)  # 10/hour
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Skip rate limiting if disabled
            if not is_rate_limiting_enabled():
                return view_func(request, *args, **kwargs)

            client_ip = get_client_ip(request)
            cache_key = f"rate_limit:{client_ip}:{view_func.__name__}"

            current_count = cache.get(cache_key, 0)

            if current_count >= max_requests:
                logger.warning(
                    f"Rate limit exceeded for IP {client_ip} on {view_func.__name__}",
                    extra={'ip': client_ip, 'count': current_count}
                )
                return Response(
                    {
                        'error': 'Rate limit exceeded',
                        'detail': f'Maximum {max_requests} requests per {window_seconds}s allowed',
                        'retry_after': window_seconds
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )

            # Increment counter
            cache.set(cache_key, current_count + 1, window_seconds)

            # Add rate limit headers to response
            response = view_func(request, *args, **kwargs)
            if hasattr(response, 'data'):
                response['X-RateLimit-Limit'] = str(max_requests)
                response['X-RateLimit-Remaining'] = str(max_requests - current_count - 1)
                response['X-RateLimit-Reset'] = str(window_seconds)

            return response

        return wrapper
    return decorator


def drf_anonymous_rate_limit(max_requests: int, window_seconds: int):
    """
    Rate limit decorator for DRF APIView/ViewSet methods.

    Args:
        max_requests: Maximum requests allowed in time window
        window_seconds: Time window in seconds

    Usage:
        class MyViewSet(viewsets.ViewSet):
            @action(methods=['post'], detail=False)
            @drf_anonymous_rate_limit(5, 3600)  # 5/hour for expensive operations
            def calculate(self, request):
                ...
    """
    def decorator(method):
        @wraps(method)
        def wrapper(self, request, *args, **kwargs):
            # Skip rate limiting if disabled
            if not is_rate_limiting_enabled():
                return method(self, request, *args, **kwargs)

            client_ip = get_client_ip(request)
            cache_key = f"rate_limit:{client_ip}:{method.__name__}"

            current_count = cache.get(cache_key, 0)

            if current_count >= max_requests:
                logger.warning(
                    f"Rate limit exceeded for IP {client_ip} on {method.__name__}",
                    extra={'ip': client_ip, 'count': current_count}
                )
                return Response(
                    {
                        'error': 'Rate limit exceeded',
                        'detail': f'Maximum {max_requests} requests per {window_seconds}s allowed',
                        'retry_after': window_seconds
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )

            cache.set(cache_key, current_count + 1, window_seconds)

            response = method(self, request, *args, **kwargs)
            if isinstance(response, Response):
                response['X-RateLimit-Limit'] = str(max_requests)
                response['X-RateLimit-Remaining'] = str(max_requests - current_count - 1)
                response['X-RateLimit-Reset'] = str(window_seconds)

            return response

        return wrapper
    return decorator


class IPRateLimitMixin:
    """
    Mixin for DRF ViewSets to add IP-based rate limiting.

    Usage:
        class MyViewSet(IPRateLimitMixin, viewsets.ViewSet):
            rate_limit_config = {
                'list': (100, 3600),      # 100 requests per hour
                'create': (10, 3600),     # 10 requests per hour
                'expensive_action': (5, 3600)  # 5 requests per hour
            }
    """

    rate_limit_config = {}

    def initial(self, request, *args, **kwargs):
        """Override initial to add rate limiting before dispatch."""
        super().initial(request, *args, **kwargs)

        # Skip rate limiting if disabled
        if not is_rate_limiting_enabled():
            return

        action_name = self.action
        if action_name and action_name in self.rate_limit_config:
            max_requests, window_seconds = self.rate_limit_config[action_name]

            client_ip = get_client_ip(request)
            cache_key = f"rate_limit:{client_ip}:{self.__class__.__name__}:{action_name}"

            current_count = cache.get(cache_key, 0)

            if current_count >= max_requests:
                logger.warning(
                    f"Rate limit exceeded for IP {client_ip} on {action_name}",
                    extra={'ip': client_ip, 'action': action_name}
                )
                raise PermissionError(f"Rate limit exceeded: {max_requests}/{window_seconds}s")

            cache.set(cache_key, current_count + 1, window_seconds)
