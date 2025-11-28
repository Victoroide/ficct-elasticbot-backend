"""
Comprehensive tests for market_data services.

Tests BinanceP2PService and DataValidator with mocked external calls.
"""
import pytest
from unittest.mock import patch

from apps.market_data.services.binance_service import BinanceP2PService
from apps.market_data.services.data_validator import DataValidator


class TestBinanceP2PService:
    """Tests for BinanceP2PService class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BinanceP2PService()

    @patch.object(BinanceP2PService, 'fetch_usdt_bob_data')
    def test_calculate_market_snapshot_success(self, mock_fetch):
        """Test complete market snapshot calculation."""
        mock_fetch.side_effect = [
            {
                'data': [
                    {
                        'adv': {
                            'price': '7.05',
                            'surplusAmount': '5000.00',
                            'advertiserNo': 'seller1'
                        }
                    }
                ]
            },
            {
                'data': [
                    {
                        'adv': {
                            'price': '6.95',
                            'tradableQuantity': '3000.00',
                            'advertiserNo': 'buyer1'
                        }
                    }
                ]
            }
        ]

        result = self.service.calculate_market_snapshot()

        assert 'average_sell_price' in result
        assert 'average_buy_price' in result
        assert 'total_volume' in result
        assert 'spread_percentage' in result
        assert result['average_sell_price'] == 7.05
        assert result['average_buy_price'] == 6.95

    @patch.object(BinanceP2PService, 'fetch_usdt_bob_data')
    def test_calculate_market_snapshot_empty_data(self, mock_fetch):
        """Test market snapshot with no ads returned."""
        mock_fetch.return_value = {'data': []}

        result = self.service.calculate_market_snapshot()

        assert result['average_sell_price'] == 0
        assert result['total_volume'] == 0

    @patch.object(BinanceP2PService, 'fetch_usdt_bob_data')
    def test_volume_calculation_accuracy(self, mock_fetch):
        """Test accurate volume aggregation."""
        mock_fetch.side_effect = [
            {
                'data': [
                    {'adv': {'price': '7.00', 'surplusAmount': '1000.50', 'advertiserNo': 'a'}},
                    {'adv': {'price': '7.05', 'surplusAmount': '2000.25', 'advertiserNo': 'b'}},
                ]
            },
            {'data': []}
        ]

        result = self.service.calculate_market_snapshot()

        assert result['total_volume'] == pytest.approx(3000.75, rel=0.01)

    @patch.object(BinanceP2PService, 'fetch_usdt_bob_data')
    def test_spread_calculation(self, mock_fetch):
        """Test spread percentage calculation."""
        mock_fetch.side_effect = [
            {'data': [{'adv': {'price': '7.10', 'surplusAmount': '1000', 'advertiserNo': 'a'}}]},
            {'data': [{'adv': {'price': '7.00', 'tradableQuantity': '1000', 'advertiserNo': 'b'}}]}
        ]

        result = self.service.calculate_market_snapshot()

        expected_spread = ((7.10 - 7.00) / 7.00) * 100
        assert result['spread_percentage'] == pytest.approx(expected_spread, rel=0.01)

    @patch.object(BinanceP2PService, 'fetch_usdt_bob_data')
    def test_num_active_traders(self, mock_fetch):
        """Test counting unique traders."""
        mock_fetch.side_effect = [
            {
                'data': [
                    {'adv': {'price': '7.00', 'surplusAmount': '1000', 'advertiserNo': 'seller1'}},
                    {'adv': {'price': '7.05', 'surplusAmount': '1000', 'advertiserNo': 'seller2'}},
                ]
            },
            {
                'data': [
                    {'adv': {'price': '6.95', 'tradableQuantity': '1000', 'advertiserNo': 'buyer1'}},
                ]
            }
        ]

        result = self.service.calculate_market_snapshot()

        assert result['num_active_traders'] == 3


class TestDataValidator:
    """Tests for DataValidator class."""

    def test_calculate_quality_score_complete_data(self):
        """Test quality score for complete high-quality data."""
        data = {
            'average_sell_price': 7.05,
            'average_buy_price': 6.98,
            'total_volume': 50000,
            'spread_percentage': 1.0,
            'num_active_traders': 15
        }

        score = DataValidator.calculate_quality_score(data)

        assert 0.8 <= score <= 1.0

    def test_calculate_quality_score_low_volume(self):
        """Test quality score for low volume data."""
        data = {
            'average_sell_price': 7.05,
            'average_buy_price': 6.98,
            'total_volume': 50,
            'spread_percentage': 1.0,
            'num_active_traders': 2
        }

        score = DataValidator.calculate_quality_score(data)

        assert score < 0.7

    def test_calculate_quality_score_price_out_of_range(self):
        """Test quality score when price is out of range."""
        data = {
            'average_sell_price': 20.00,
            'average_buy_price': 19.50,
            'total_volume': 50000,
            'spread_percentage': 1.0,
            'num_active_traders': 10
        }

        score = DataValidator.calculate_quality_score(data)

        assert score < 1.0

    def test_calculate_quality_score_wide_spread(self):
        """Test quality score with wide spread."""
        data = {
            'average_sell_price': 7.05,
            'average_buy_price': 6.50,
            'total_volume': 50000,
            'spread_percentage': 8.0,
            'num_active_traders': 10
        }

        score = DataValidator.calculate_quality_score(data)

        assert score < 1.0

    def test_is_valid_high_quality(self):
        """Test is_valid returns True for high quality data."""
        data = {
            'average_sell_price': 7.05,
            'average_buy_price': 6.98,
            'total_volume': 50000,
            'spread_percentage': 1.0,
            'num_active_traders': 15
        }

        assert DataValidator.is_valid(data) is True

    def test_is_valid_low_quality(self):
        """Test is_valid returns False for low quality data."""
        data = {
            'average_sell_price': 20.00,
            'average_buy_price': 19.50,
            'total_volume': 50,
            'spread_percentage': 10.0,
            'num_active_traders': 2
        }

        assert DataValidator.is_valid(data) is False
