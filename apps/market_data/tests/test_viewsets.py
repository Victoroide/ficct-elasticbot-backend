"""
Comprehensive tests for market_data viewsets.

Tests SnapshotViewSet API endpoints.
"""
import pytest
from decimal import Decimal
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.market_data.models import MarketSnapshot


@pytest.mark.django_db
class TestSnapshotViewSet:
    """Tests for SnapshotViewSet API endpoints."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = APIClient()

    def _create_snapshot(self, hours_ago=0, quality_score=0.92):
        """Helper to create a snapshot."""
        return MarketSnapshot.objects.create(
            timestamp=timezone.now() - timezone.timedelta(hours=hours_ago),
            average_sell_price=Decimal('7.05'),
            average_buy_price=Decimal('6.98'),
            total_volume=Decimal('50000.00'),
            spread_percentage=Decimal('1.00'),
            num_active_traders=15,
            data_quality_score=Decimal(str(quality_score))
        )

    def test_list_snapshots_empty(self):
        """Test listing snapshots when none exist."""
        response = self.client.get('/api/v1/market-data/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 0
        assert response.data['results'] == []

    def test_list_snapshots_with_data(self):
        """Test listing snapshots with data."""
        self._create_snapshot(hours_ago=0)
        self._create_snapshot(hours_ago=1)
        self._create_snapshot(hours_ago=2)

        response = self.client.get('/api/v1/market-data/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 3

    def test_list_snapshots_pagination(self):
        """Test pagination of snapshots."""
        for i in range(60):
            self._create_snapshot(hours_ago=i)

        response = self.client.get('/api/v1/market-data/')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 50
        assert response.data['next'] is not None

    def test_list_snapshots_filters_low_quality(self):
        """Test that low quality snapshots are filtered."""
        self._create_snapshot(hours_ago=0, quality_score=0.92)
        self._create_snapshot(hours_ago=1, quality_score=0.50)

        response = self.client.get('/api/v1/market-data/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 1

    def test_latest_snapshot_success(self):
        """Test getting latest snapshot."""
        self._create_snapshot(hours_ago=2)
        latest = self._create_snapshot(hours_ago=0)

        response = self.client.get('/api/v1/market-data/latest/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == latest.id

    def test_latest_snapshot_empty(self):
        """Test latest endpoint when no snapshots exist."""
        response = self.client.get('/api/v1/market-data/latest/')

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'error' in response.data

    def test_retrieve_single_snapshot(self):
        """Test retrieving a single snapshot by ID."""
        snapshot = self._create_snapshot()

        response = self.client.get(f'/api/v1/market-data/{snapshot.id}/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == snapshot.id
        assert float(response.data['average_sell_price']) == 7.05

    def test_snapshot_response_format(self):
        """Test response serialization format."""
        snapshot = self._create_snapshot()

        response = self.client.get(f'/api/v1/market-data/{snapshot.id}/')

        assert 'id' in response.data
        assert 'timestamp' in response.data
        assert 'average_sell_price' in response.data
        assert 'average_buy_price' in response.data
        assert 'total_volume' in response.data
        assert 'spread_percentage' in response.data
        assert 'num_active_traders' in response.data
        assert 'data_quality_score' in response.data

    def test_anonymous_access_allowed(self):
        """Test that anonymous access is allowed."""
        self._create_snapshot()

        response = self.client.get('/api/v1/market-data/')

        assert response.status_code == status.HTTP_200_OK

    def test_ordering_by_timestamp(self):
        """Test snapshots are ordered by timestamp descending."""
        old = self._create_snapshot(hours_ago=5)
        middle = self._create_snapshot(hours_ago=2)
        new = self._create_snapshot(hours_ago=0)

        response = self.client.get('/api/v1/market-data/')

        results = response.data['results']
        assert results[0]['id'] == new.id
        assert results[1]['id'] == middle.id
        assert results[2]['id'] == old.id
