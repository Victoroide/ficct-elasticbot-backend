"""
Tests for BCB exchange rate scraping service.

Tests the production-grade BCB scraper that uses:
https://www.bcb.gob.bo/librerias/indicadores/otras/ultimo.php
"""
import pytest
from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import patch, Mock
import requests

from apps.market_data.services.bcb_service import BCBService, get_bcb_service


class TestBCBServiceInit:
    """Test BCBService initialization."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BCBService()

    def test_init_creates_session(self):
        """Test that __init__ creates a requests session."""
        assert self.service.session is not None
        assert isinstance(self.service.session, requests.Session)

    def test_session_has_retry_adapter(self):
        """Test that session has retry adapter configured."""
        adapters = self.service.session.adapters
        assert 'http://' in adapters
        assert 'https://' in adapters

    def test_session_has_user_agent(self):
        """Test that session has User-Agent header."""
        assert 'User-Agent' in self.service.session.headers
        assert 'Mozilla' in self.service.session.headers['User-Agent']

    def test_bcb_url_is_ultimo_php(self):
        """Test that BCB URL points to ultimo.php endpoint."""
        assert 'ultimo.php' in self.service.BCB_URL
        assert 'bcb.gob.bo' in self.service.BCB_URL


class TestParseBCBTable:
    """Test HTML table parsing from BCB ultimo.php page."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BCBService()

    def test_parse_valid_bcb_table(self):
        """Test parsing of valid BCB HTML table structure."""
        # Matches actual BCB ultimo.php format
        html = b'''
        <table>
            <tr>
                <td>ESTADOS UNIDOS</td>
                <td>DOLAR VENTA</td>
                <td>USD.VENTA</td>
                <td>6.96</td>
            </tr>
            <tr>
                <td>ESTADOS UNIDOS</td>
                <td>DOLAR COMPRA</td>
                <td>USD.COMPRA</td>
                <td>6.86</td>
            </tr>
        </table>
        '''
        rates = self.service._parse_bcb_table(html)

        assert rates['venta'] == Decimal('6.96')
        assert rates['compra'] == Decimal('6.86')

    def test_parse_table_with_accented_dolar(self):
        """Test parsing with accented DÓLAR."""
        html = b'''
        <table>
            <tr>
                <td>ESTADOS UNIDOS</td>
                <td>D\xc3\x93LAR VENTA</td>
                <td>USD.VENTA</td>
                <td>6.96</td>
            </tr>
            <tr>
                <td>ESTADOS UNIDOS</td>
                <td>D\xc3\x93LAR COMPRA</td>
                <td>USD.COMPRA</td>
                <td>6.86</td>
            </tr>
        </table>
        '''
        rates = self.service._parse_bcb_table(html)

        assert rates['venta'] == Decimal('6.96')
        assert rates['compra'] == Decimal('6.86')

    def test_parse_table_no_table_raises(self):
        """Test that missing table raises ValueError."""
        html = b'<html><body>No table here</body></html>'

        with pytest.raises(ValueError, match="No table found"):
            self.service._parse_bcb_table(html)

    def test_parse_table_missing_venta_raises(self):
        """Test that missing VENTA rate raises ValueError."""
        html = b'''
        <table>
            <tr>
                <td>ESTADOS UNIDOS</td>
                <td>DOLAR COMPRA</td>
                <td>USD.COMPRA</td>
                <td>6.86</td>
            </tr>
        </table>
        '''
        with pytest.raises(ValueError, match="VENTA rate not found"):
            self.service._parse_bcb_table(html)

    def test_parse_table_missing_compra_raises(self):
        """Test that missing COMPRA rate raises ValueError."""
        html = b'''
        <table>
            <tr>
                <td>ESTADOS UNIDOS</td>
                <td>DOLAR VENTA</td>
                <td>USD.VENTA</td>
                <td>6.96</td>
            </tr>
        </table>
        '''
        with pytest.raises(ValueError, match="COMPRA rate not found"):
            self.service._parse_bcb_table(html)

    def test_parse_table_ignores_non_usd_rows(self):
        """Test that non-USD rows are ignored."""
        html = b'''
        <table>
            <tr>
                <td>EUROPA</td>
                <td>EURO VENTA</td>
                <td>EUR.VENTA</td>
                <td>7.50</td>
            </tr>
            <tr>
                <td>ESTADOS UNIDOS</td>
                <td>DOLAR VENTA</td>
                <td>USD.VENTA</td>
                <td>6.96</td>
            </tr>
            <tr>
                <td>ESTADOS UNIDOS</td>
                <td>DOLAR COMPRA</td>
                <td>USD.COMPRA</td>
                <td>6.86</td>
            </tr>
        </table>
        '''
        rates = self.service._parse_bcb_table(html)

        assert rates['venta'] == Decimal('6.96')
        assert rates['compra'] == Decimal('6.86')


class TestCleanRateValue:
    """Test rate text cleaning and conversion."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BCBService()

    def test_clean_simple_rate(self):
        """Test cleaning simple rate format."""
        result = self.service._clean_rate_value('6.96')
        assert result == Decimal('6.96')

    def test_clean_rate_with_comma(self):
        """Test cleaning European format with comma."""
        result = self.service._clean_rate_value('6,96')
        assert result == Decimal('6.96')

    def test_clean_rate_with_whitespace(self):
        """Test cleaning rate with whitespace."""
        result = self.service._clean_rate_value('  6.96  ')
        assert result == Decimal('6.96')

    def test_clean_rate_with_currency_symbol(self):
        """Test cleaning rate with Bs. prefix."""
        result = self.service._clean_rate_value('Bs. 6.96')
        assert result == Decimal('6.96')

    def test_clean_rate_with_bob(self):
        """Test cleaning rate with BOB suffix."""
        result = self.service._clean_rate_value('6.96 BOB')
        assert result == Decimal('6.96')

    def test_clean_empty_raises(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="Empty rate text"):
            self.service._clean_rate_value('')

    def test_clean_no_number_raises(self):
        """Test that text without number raises ValueError."""
        with pytest.raises(ValueError, match="Cannot extract rate"):
            self.service._clean_rate_value('abc')


class TestValidateRate:
    """Test rate validation logic."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BCBService()

    def test_validate_rate_valid(self):
        """Test validation passes for valid rate."""
        # Should not raise
        self.service._validate_rate(Decimal('6.96'), 'venta')

    def test_validate_rate_at_minimum(self):
        """Test validation passes at minimum boundary."""
        self.service._validate_rate(Decimal('6.50'), 'venta')

    def test_validate_rate_at_maximum(self):
        """Test validation passes at maximum boundary."""
        self.service._validate_rate(Decimal('7.50'), 'venta')

    def test_validate_rate_below_minimum_raises(self):
        """Test validation fails below minimum."""
        with pytest.raises(ValueError, match="below minimum"):
            self.service._validate_rate(Decimal('5.00'), 'venta')

    def test_validate_rate_above_maximum_raises(self):
        """Test validation fails above maximum."""
        with pytest.raises(ValueError, match="above maximum"):
            self.service._validate_rate(Decimal('10.00'), 'venta')

    def test_validate_rate_wrong_type_raises(self):
        """Test validation fails for non-Decimal type."""
        with pytest.raises(ValueError, match="must be Decimal"):
            self.service._validate_rate(6.96, 'venta')


class TestValidateRateConsistency:
    """Test rate consistency validation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BCBService()

    def test_valid_consistency(self):
        """Test valid buy/sell rate relationship."""
        # Should not raise
        self.service._validate_rate_consistency(
            Decimal('6.96'), Decimal('6.86')
        )

    def test_buy_equals_sell_raises(self):
        """Test that equal rates raise ValueError."""
        with pytest.raises(ValueError, match="must be less than"):
            self.service._validate_rate_consistency(
                Decimal('6.96'), Decimal('6.96')
            )

    def test_buy_greater_than_sell_raises(self):
        """Test that buy > sell raises ValueError."""
        with pytest.raises(ValueError, match="must be less than"):
            self.service._validate_rate_consistency(
                Decimal('6.86'), Decimal('6.96')
            )


class TestFetchExchangeRate:
    """Test main fetch method with mocked HTTP."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BCBService()
        # Reduce retries for faster tests
        self.service.max_retries = 1
        self.service.retry_delays = [0]

    @patch('requests.Session.get')
    def test_fetch_success(self, mock_get):
        """Test successful fetch from BCB."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'''
        <table>
            <tr>
                <td>ESTADOS UNIDOS</td>
                <td>DOLAR VENTA</td>
                <td>USD.VENTA</td>
                <td>6.96</td>
            </tr>
            <tr>
                <td>ESTADOS UNIDOS</td>
                <td>DOLAR COMPRA</td>
                <td>USD.COMPRA</td>
                <td>6.86</td>
            </tr>
        </table>
        '''
        mock_response.elapsed = Mock()
        mock_response.elapsed.total_seconds.return_value = 0.5
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = self.service.fetch_exchange_rate()

        assert result['success'] is True
        assert result['rate'] == Decimal('6.96')
        assert result['rate_compra'] == Decimal('6.86')
        assert result['source'] == 'BCB_ULTIMO_PHP'
        mock_get.assert_called_once()

    @patch('requests.Session.get')
    def test_fetch_timeout_uses_fallback(self, mock_get):
        """Test timeout triggers fallback."""
        mock_get.side_effect = requests.Timeout()

        result = self.service.fetch_exchange_rate()

        assert result['success'] is True
        # Falls back to emergency rate
        assert result['rate'] == Decimal('6.96')
        assert 'FALLBACK' in result['source'] or 'CACHED' in result['source']

    @patch('requests.Session.get')
    def test_fetch_connection_error_uses_fallback(self, mock_get):
        """Test connection error triggers fallback."""
        mock_get.side_effect = requests.ConnectionError()

        result = self.service.fetch_exchange_rate()

        assert result['success'] is True
        assert result['rate'] == Decimal('6.96')

    @patch('requests.Session.get')
    def test_fetch_http_error_uses_fallback(self, mock_get):
        """Test HTTP error triggers fallback."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.HTTPError(
            response=mock_response
        )
        mock_get.return_value = mock_response

        result = self.service.fetch_exchange_rate()

        assert result['success'] is True
        assert result['rate'] == Decimal('6.96')


class TestGetFallbackRate:
    """Test fallback rate retrieval."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BCBService()

    @pytest.mark.django_db
    def test_fallback_uses_cached_rate(self):
        """Test fallback retrieves cached rate from database."""
        from apps.market_data.models import MacroeconomicIndicator

        # Create a cached rate
        MacroeconomicIndicator.objects.create(
            date=date.today() - timedelta(days=1),
            official_exchange_rate=Decimal('6.97'),
            source='BCB'
        )

        result = self.service._get_fallback_rate()

        assert result['success'] is True
        assert result['rate'] == Decimal('6.97')
        assert result['source'] == 'BCB_CACHED'

    @pytest.mark.django_db
    def test_fallback_emergency_when_no_cache(self):
        """Test emergency fallback when no cached rate."""
        from apps.market_data.models import MacroeconomicIndicator

        # Ensure no cached rates
        MacroeconomicIndicator.objects.filter(
            official_exchange_rate__isnull=False
        ).delete()

        result = self.service._get_fallback_rate()

        assert result['success'] is True
        assert result['rate'] == Decimal('6.96')
        assert result['source'] == 'BCB_EMERGENCY_FALLBACK'


class TestSaveRate:
    """Test database storage."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BCBService()

    @pytest.mark.django_db
    def test_save_creates_new_record(self):
        """Test saving creates new MacroeconomicIndicator."""
        from apps.market_data.models import MacroeconomicIndicator

        # Ensure no record for today
        MacroeconomicIndicator.objects.filter(date=date.today()).delete()

        indicator = self.service.save_rate(
            Decimal('6.96'), Decimal('6.86')
        )

        assert indicator is not None
        assert indicator.official_exchange_rate == Decimal('6.96')
        assert indicator.source == 'BCB'
        assert indicator.date == date.today()

    @pytest.mark.django_db
    def test_save_updates_existing_record(self):
        """Test saving updates existing record for today."""
        from apps.market_data.models import MacroeconomicIndicator

        # Create existing record
        existing = MacroeconomicIndicator.objects.create(
            date=date.today(),
            official_exchange_rate=Decimal('6.90'),
            source='BCB'
        )

        indicator = self.service.save_rate(
            Decimal('6.96'), Decimal('6.86')
        )

        assert indicator.pk == existing.pk
        assert indicator.official_exchange_rate == Decimal('6.96')


class TestBCBServiceSingleton:
    """Test BCB service singleton pattern."""

    def test_get_bcb_service_returns_instance(self):
        """Test that get_bcb_service returns a BCBService instance."""
        service = get_bcb_service()
        assert isinstance(service, BCBService)

    def test_get_bcb_service_returns_same_instance(self):
        """Test that get_bcb_service returns singleton."""
        service1 = get_bcb_service()
        service2 = get_bcb_service()
        assert service1 is service2
