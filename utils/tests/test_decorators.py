"""
Comprehensive tests for utils decorators.

Tests rate limiting decorators and helpers.
"""
from unittest.mock import patch
from django.test import RequestFactory
from rest_framework import status

from utils.decorators import (
    get_client_ip,
    anonymous_rate_limit,
    drf_anonymous_rate_limit,
    IPRateLimitMixin
)


class TestGetClientIP:
    """Tests for get_client_ip helper function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_get_ip_from_remote_addr(self):
        """Test getting IP from REMOTE_ADDR."""
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '192.168.1.100'

        ip = get_client_ip(request)

        assert ip == '192.168.1.100'

    def test_get_ip_from_x_forwarded_for(self):
        """Test getting IP from X-Forwarded-For header."""
        request = self.factory.get('/')
        request.META['HTTP_X_FORWARDED_FOR'] = '10.0.0.1, 192.168.1.1'
        request.META['REMOTE_ADDR'] = '127.0.0.1'

        ip = get_client_ip(request)

        assert ip == '10.0.0.1'

    def test_get_ip_x_forwarded_for_priority(self):
        """Test that X-Forwarded-For takes priority."""
        request = self.factory.get('/')
        request.META['HTTP_X_FORWARDED_FOR'] = '203.0.113.50'
        request.META['REMOTE_ADDR'] = '10.0.0.1'

        ip = get_client_ip(request)

        assert ip == '203.0.113.50'

    def test_get_ip_default_localhost(self):
        """Test default to localhost when no IP available."""
        request = self.factory.get('/')
        request.META.pop('REMOTE_ADDR', None)

        ip = get_client_ip(request)

        assert ip == '127.0.0.1'

    def test_get_ip_strips_whitespace(self):
        """Test that IP addresses are stripped of whitespace."""
        request = self.factory.get('/')
        request.META['HTTP_X_FORWARDED_FOR'] = '  10.0.0.1  , 192.168.1.1'

        ip = get_client_ip(request)

        assert ip == '10.0.0.1'


class TestAnonymousRateLimit:
    """Tests for anonymous_rate_limit decorator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    @patch('utils.decorators.cache')
    def test_allows_requests_under_limit(self, mock_cache):
        """Test that requests under limit are allowed."""
        mock_cache.get.return_value = 5

        @anonymous_rate_limit(max_requests=10, window_seconds=3600)
        def test_view(request):
            from rest_framework.response import Response
            return Response({'success': True})

        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '192.168.1.1'

        response = test_view(request)

        assert response.data == {'success': True}

    @patch('utils.decorators.is_rate_limiting_enabled', return_value=True)
    @patch('utils.decorators.cache')
    def test_blocks_requests_over_limit(self, mock_cache, mock_rate_limit_enabled):
        """Test that requests over limit are blocked."""
        mock_cache.get.return_value = 10

        @anonymous_rate_limit(max_requests=10, window_seconds=3600)
        def test_view(request):
            from rest_framework.response import Response
            return Response({'success': True})

        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '192.168.1.1'

        response = test_view(request)

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    @patch('utils.decorators.is_rate_limiting_enabled', return_value=True)
    @patch('utils.decorators.cache')
    def test_increments_counter(self, mock_cache, mock_rate_limit_enabled):
        """Test that counter is incremented."""
        mock_cache.get.return_value = 0

        @anonymous_rate_limit(max_requests=10, window_seconds=3600)
        def test_view(request):
            from rest_framework.response import Response
            return Response({'success': True})

        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '192.168.1.1'

        test_view(request)

        mock_cache.set.assert_called_once()

    @patch('utils.decorators.is_rate_limiting_enabled', return_value=True)
    @patch('utils.decorators.cache')
    def test_rate_limit_headers(self, mock_cache, mock_rate_limit_enabled):
        """Test that rate limit headers are added."""
        mock_cache.get.return_value = 3

        @anonymous_rate_limit(max_requests=10, window_seconds=3600)
        def test_view(request):
            from rest_framework.response import Response
            return Response({'success': True})

        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '192.168.1.1'

        response = test_view(request)

        assert response['X-RateLimit-Limit'] == '10'
        assert response['X-RateLimit-Remaining'] == '6'


class TestDRFAnonymousRateLimit:
    """Tests for drf_anonymous_rate_limit decorator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    @patch('utils.decorators.cache')
    def test_allows_requests_under_limit(self, mock_cache):
        """Test that requests under limit are allowed."""
        mock_cache.get.return_value = 2

        class MockViewSet:
            @drf_anonymous_rate_limit(max_requests=5, window_seconds=3600)
            def action(self, request):
                from rest_framework.response import Response
                return Response({'success': True})

        viewset = MockViewSet()
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '192.168.1.1'

        response = viewset.action(request)

        assert response.data == {'success': True}

    @patch('utils.decorators.is_rate_limiting_enabled', return_value=True)
    @patch('utils.decorators.cache')
    def test_blocks_requests_over_limit(self, mock_cache, mock_rate_limit_enabled):
        """Test that requests over limit are blocked."""
        mock_cache.get.return_value = 5

        class MockViewSet:
            @drf_anonymous_rate_limit(max_requests=5, window_seconds=3600)
            def action(self, request):
                from rest_framework.response import Response
                return Response({'success': True})

        viewset = MockViewSet()
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '192.168.1.1'

        response = viewset.action(request)

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


class TestIPRateLimitMixin:
    """Tests for IPRateLimitMixin class."""

    def test_mixin_has_rate_limit_config(self):
        """Test that mixin provides rate_limit_config."""
        class TestViewSet(IPRateLimitMixin):
            pass

        viewset = TestViewSet()

        assert hasattr(viewset, 'rate_limit_config')
        assert isinstance(viewset.rate_limit_config, dict)

    def test_mixin_config_structure(self):
        """Test that mixin config can be customized."""
        class TestViewSet(IPRateLimitMixin):
            rate_limit_config = {
                'list': (100, 3600),
                'create': (10, 3600)
            }

        viewset = TestViewSet()

        assert viewset.rate_limit_config['list'] == (100, 3600)
        assert viewset.rate_limit_config['create'] == (10, 3600)
