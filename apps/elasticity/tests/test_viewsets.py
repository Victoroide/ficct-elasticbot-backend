"""
Comprehensive tests for elasticity viewsets.

Tests CalculationViewSet API endpoints.
"""
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.elasticity.models import ElasticityCalculation


@pytest.mark.django_db
class TestCalculationViewSet:
    """Tests for CalculationViewSet API endpoints."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = APIClient()

    def _create_calculation(self, status_val='COMPLETED', client_ip='127.0.0.1'):
        """Helper to create a calculation."""
        return ElasticityCalculation.objects.create(
            method='MIDPOINT',
            start_date=timezone.now() - timezone.timedelta(days=7),
            end_date=timezone.now(),
            window_size='DAILY',
            status=status_val,
            elasticity_coefficient=Decimal('-0.8734') if status_val == 'COMPLETED' else None,
            classification='INELASTIC' if status_val == 'COMPLETED' else None,
            client_ip=client_ip
        )

    def test_list_calculations(self):
        """Test listing calculations."""
        self._create_calculation()
        self._create_calculation()

        response = self.client.get('/api/v1/elasticity/')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 2

    def test_retrieve_calculation(self):
        """Test retrieving a single calculation."""
        calc = self._create_calculation()

        response = self.client.get(f'/api/v1/elasticity/{calc.id}/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == str(calc.id)

    def test_retrieve_nonexistent_calculation(self):
        """Test retrieving nonexistent calculation returns 404."""
        import uuid
        fake_id = uuid.uuid4()

        response = self.client.get(f'/api/v1/elasticity/{fake_id}/')

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('apps.elasticity.viewsets.calculation_viewset.calculate_elasticity_async')
    def test_create_calculation(self, mock_task):
        """Test creating a new calculation."""
        mock_task.delay = MagicMock()

        response = self.client.post('/api/v1/elasticity/calculate/', {
            'method': 'midpoint',
            'start_date': '2025-11-01T00:00:00Z',
            'end_date': '2025-11-18T23:59:59Z',
            'window_size': 'daily'
        }, format='json')

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert 'id' in response.data
        assert response.data['status'] == 'PENDING'
        mock_task.delay.assert_called_once()

    @patch('apps.elasticity.viewsets.calculation_viewset.calculate_elasticity_async')
    def test_create_calculation_regression_method(self, mock_task):
        """Test creating calculation with regression method."""
        mock_task.delay = MagicMock()

        response = self.client.post('/api/v1/elasticity/calculate/', {
            'method': 'regression',
            'start_date': '2025-11-01T00:00:00Z',
            'end_date': '2025-11-18T23:59:59Z',
            'window_size': 'hourly'
        }, format='json')

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data['method'] == 'REGRESSION'

    def test_create_calculation_invalid_method(self):
        """Test creating calculation with invalid method."""
        response = self.client.post('/api/v1/elasticity/calculate/', {
            'method': 'invalid',
            'start_date': '2025-11-01T00:00:00Z',
            'end_date': '2025-11-18T23:59:59Z',
            'window_size': 'daily'
        }, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_calculation_missing_fields(self):
        """Test creating calculation with missing fields."""
        response = self.client.post('/api/v1/elasticity/calculate/', {
            'method': 'midpoint'
        }, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_recent_calculations_by_ip(self):
        """Test recent calculations filtered by client IP."""
        self._create_calculation(client_ip='192.168.1.1')
        self._create_calculation(client_ip='192.168.1.1')
        self._create_calculation(client_ip='10.0.0.1')

        response = self.client.get('/api/v1/elasticity/recent/',
                                   REMOTE_ADDR='192.168.1.1')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2

    def test_calculation_status_endpoint(self):
        """Test calculation status endpoint."""
        calc = self._create_calculation(status_val='PROCESSING')

        response = self.client.get(f'/api/v1/elasticity/{calc.id}/status/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'PROCESSING'
        assert response.data['is_complete'] is False

    def test_calculation_status_completed(self):
        """Test calculation status for completed calculation."""
        calc = self._create_calculation(status_val='COMPLETED')

        response = self.client.get(f'/api/v1/elasticity/{calc.id}/status/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_complete'] is True

    def test_anonymous_access_allowed(self):
        """Test that anonymous access is allowed."""
        self._create_calculation()

        response = self.client.get('/api/v1/elasticity/')

        assert response.status_code == status.HTTP_200_OK

    def test_calculation_response_format(self):
        """Test response serialization format."""
        calc = self._create_calculation()

        response = self.client.get(f'/api/v1/elasticity/{calc.id}/')

        assert 'id' in response.data
        assert 'method' in response.data
        assert 'status' in response.data
        assert 'elasticity_coefficient' in response.data
        assert 'classification' in response.data

    def test_ordering_by_created_at(self):
        """Test calculations are ordered by created_at descending."""
        old = self._create_calculation()
        new = self._create_calculation()

        response = self.client.get('/api/v1/elasticity/')

        results = response.data['results']
        assert results[0]['id'] == str(new.id)
        assert results[1]['id'] == str(old.id)
