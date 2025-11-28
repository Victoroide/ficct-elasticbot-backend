"""
BCB (Banco Central de Bolivia) exchange rate scraping service.

Fetches official BOB/USD exchange rates from the BCB lightweight indicators page.
Uses the verified stable endpoint designed for system integration.

Source: https://www.bcb.gob.bo/librerias/indicadores/otras/ultimo.php
"""
import re
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import date, datetime, timezone
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class BCBService:
    """
    Service for fetching official USD/BOB exchange rate from BCB.

    Uses BCB's lightweight indicators page designed for system integration:
    https://www.bcb.gob.bo/librerias/indicadores/otras/ultimo.php

    Strategy:
    1. Primary: HTML scraping from ultimo.php (stable, lightweight)
    2. Fallback: Cached rate from database (max 7 days old)
    3. Emergency: Known fixed rate (6.96 BOB/USD since 2011)

    The page contains a table with USD buy/sell rates in format:
    | ESTADOS UNIDOS | DOLAR | VENTA  | 6.96 |
    | ESTADOS UNIDOS | DOLAR | COMPRA | 6.86 |
    """

    # Official BCB lightweight indicators endpoint (verified working)
    BCB_URL = "https://www.bcb.gob.bo/librerias/indicadores/otras/ultimo.php"

    # Validation bounds (BOB per USD)
    # Historical official rate is ~6.96 BOB/USD (fixed since 2011)
    MIN_RATE = Decimal("6.50")
    MAX_RATE = Decimal("7.50")

    # Spread validation (difference between sell and buy rate)
    MIN_SPREAD = Decimal("0.05")
    MAX_SPREAD = Decimal("0.30")

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAYS = [2, 5, 10]  # seconds between attempts
    TIMEOUT = (5, 15)  # (connect, read) timeouts

    def __init__(self):
        """Initialize BCB service with configured HTTP session."""
        self.session = self._create_session()
        self.max_retries = self.MAX_RETRIES
        self.retry_delays = self.RETRY_DELAYS
        self.timeout = self.TIMEOUT

    def _create_session(self) -> requests.Session:
        """
        Create requests session with retry logic and browser-like headers.

        Returns:
            Configured requests.Session with retry adapter
        """
        session = requests.Session()

        # Configure retry strategy for transport-level errors
        retry_strategy = Retry(
            total=2,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Browser-like headers to prevent blocking
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-BO,es;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Cache-Control": "max-age=0",
        })

        return session

    def fetch_exchange_rate(self) -> Dict[str, Any]:
        """
        Fetch official exchange rate from BCB with retry logic.

        Scrapes BCB's lightweight indicators page and extracts USD rates.
        Uses VENTA (sell) rate as the official exchange rate.

        Returns:
            dict: {
                'success': bool,
                'rate': Decimal (VENTA rate),
                'rate_compra': Decimal (COMPRA rate),
                'date': date,
                'source': str,
                'raw_data': dict,
                'error': str or None
            }
        """
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    f"BCB fetch attempt {attempt}/{self.max_retries}",
                    extra={'url': self.BCB_URL}
                )

                # Make HTTP request
                response = self.session.get(
                    self.BCB_URL,
                    timeout=self.timeout,
                    allow_redirects=True
                )
                response.raise_for_status()

                logger.debug(
                    "BCB response received",
                    extra={
                        'status_code': response.status_code,
                        'content_length': len(response.content),
                        'elapsed_ms': response.elapsed.total_seconds() * 1000
                    }
                )

                # Parse HTML table
                rates = self._parse_bcb_table(response.content)

                # Validate individual rates
                self._validate_rate(rates['venta'], 'venta')
                self._validate_rate(rates['compra'], 'compra')

                # Validate rate consistency (buy < sell)
                self._validate_rate_consistency(rates['venta'], rates['compra'])

                logger.info(
                    "BCB rate fetched successfully",
                    extra={
                        'venta': str(rates['venta']),
                        'compra': str(rates['compra']),
                        'attempt': attempt
                    }
                )

                return {
                    'success': True,
                    'rate': rates['venta'],  # Official rate is VENTA
                    'rate_compra': rates['compra'],
                    'date': date.today(),
                    'source': 'BCB_ULTIMO_PHP',
                    'raw_data': {
                        'venta': str(rates['venta']),
                        'compra': str(rates['compra']),
                        'url': self.BCB_URL,
                        'scraped_at': datetime.now(timezone.utc).isoformat()
                    },
                    'error': None
                }

            except requests.Timeout as e:
                last_error = f"Connection timeout: {e}"
                logger.warning(
                    f"BCB request timeout (attempt {attempt})",
                    extra={'error': str(e)}
                )

            except requests.ConnectionError as e:
                last_error = f"Connection error: {e}"
                logger.warning(
                    f"BCB connection error (attempt {attempt})",
                    extra={'error': str(e)}
                )

            except requests.HTTPError as e:
                status = e.response.status_code if e.response else 'unknown'
                last_error = f"HTTP error {status}: {e}"
                logger.error(f"BCB HTTP error: {status}", extra={'error': str(e)})
                # Don't retry on 4xx client errors
                if e.response and 400 <= e.response.status_code < 500:
                    break

            except ValueError as e:
                # Parsing or validation error - page structure may have changed
                last_error = f"Parse/validation error: {e}"
                logger.error(f"BCB parsing error: {e}")
                break  # Don't retry parsing errors

            except Exception as e:
                last_error = f"Unexpected error: {e}"
                logger.error(f"Unexpected BCB error: {e}", exc_info=True)
                break

            # Wait before retry (if not last attempt)
            if attempt < self.max_retries:
                delay = self.retry_delays[attempt - 1]
                logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)

        # All attempts failed - use fallback
        logger.warning("All BCB fetch attempts failed, using fallback")
        return self._get_fallback_rate(last_error)

    def _parse_bcb_table(self, html_content: bytes) -> Dict[str, Decimal]:
        """
        Extract USD exchange rates from BCB HTML table.

        Parses the ultimo.php page which contains rows like:
        | ESTADOS UNIDOS | DOLAR VENTA  | USD.VENTA  | 6.96 |
        | ESTADOS UNIDOS | DOLAR COMPRA | USD.COMPRA | 6.86 |

        Args:
            html_content: Raw HTML bytes from BCB page

        Returns:
            dict: {'venta': Decimal, 'compra': Decimal}

        Raises:
            ValueError: If rates cannot be extracted
        """
        soup = BeautifulSoup(html_content, 'lxml')

        # Find all tables (main rate table may not be the first)
        tables = soup.find_all('table')
        if not tables:
            raise ValueError("No table found on BCB page")

        rates: Dict[str, Optional[Decimal]] = {'venta': None, 'compra': None}

        # Search through all tables for USD rates
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 2:
                    continue  # Skip header or malformed rows

                # Extract and normalize row text
                row_text = " ".join(
                    [col.get_text().strip() for col in cols]
                ).upper()

                # Check if this row is about USD
                if "ESTADOS UNIDOS" not in row_text:
                    continue
                if "DOLAR" not in row_text and "DÓLAR" not in row_text:
                    continue

                # Find the rate value - look for numeric column
                # The rate is typically in column index 3 (4th column)
                rate_text = None
                for col in reversed(cols):
                    col_text = col.get_text().strip()
                    # Check if this looks like a rate (number with decimals)
                    if re.match(r'^\d+[.,]\d+$', col_text):
                        rate_text = col_text
                        break

                if rate_text is None:
                    continue

                # Determine rate type from row text
                # BCB uses "DOLAR VENTA" and "DOLAR COMPRA" format
                if "VENTA" in row_text and rates['venta'] is None:
                    rates['venta'] = self._clean_rate_value(rate_text)
                elif "COMPRA" in row_text and rates['compra'] is None:
                    rates['compra'] = self._clean_rate_value(rate_text)

            # If both rates found, no need to check more tables
            if rates['venta'] is not None and rates['compra'] is not None:
                break

        # Validate both rates were found
        if rates['venta'] is None:
            raise ValueError("VENTA rate not found in BCB table")
        if rates['compra'] is None:
            raise ValueError("COMPRA rate not found in BCB table")

        return {'venta': rates['venta'], 'compra': rates['compra']}

    def _clean_rate_value(self, text: str) -> Decimal:
        """
        Clean and convert rate text to Decimal.

        Handles various formats:
        - "6.96" → Decimal('6.96')
        - "6,96" → Decimal('6.96')
        - " 6.96 " → Decimal('6.96')
        - "Bs. 6.96" → Decimal('6.96')

        Args:
            text: Raw rate text from HTML

        Returns:
            Decimal: Cleaned rate value

        Raises:
            ValueError: If rate cannot be extracted
        """
        if not text:
            raise ValueError("Empty rate text")

        # Remove whitespace and currency symbols
        clean = text.strip()
        clean = clean.replace('Bs.', '').replace('BOB', '').replace('USD', '')
        clean = clean.replace(',', '.')  # European format
        clean = clean.strip()

        # Extract numeric value with regex
        match = re.search(r'(\d+\.?\d*)', clean)
        if not match:
            raise ValueError(f"Cannot extract rate from: {text}")

        try:
            rate = Decimal(match.group(1))
            # Ensure 2 decimal places
            return rate.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except InvalidOperation as e:
            raise ValueError(f"Invalid decimal value: {text}") from e

    def _validate_rate(self, rate: Decimal, rate_type: str) -> None:
        """
        Validate exchange rate is within expected bounds.

        Args:
            rate: Exchange rate to validate
            rate_type: 'venta' or 'compra' (for error messages)

        Raises:
            ValueError: If validation fails
        """
        if not isinstance(rate, Decimal):
            raise ValueError(f"{rate_type} rate must be Decimal, got {type(rate)}")

        if rate < self.MIN_RATE:
            raise ValueError(
                f"{rate_type} rate {rate} below minimum {self.MIN_RATE}"
            )

        if rate > self.MAX_RATE:
            raise ValueError(
                f"{rate_type} rate {rate} above maximum {self.MAX_RATE}"
            )

    def _validate_rate_consistency(
        self, venta: Decimal, compra: Decimal
    ) -> None:
        """
        Validate relationship between buy and sell rates.

        Args:
            venta: Sell rate (should be higher)
            compra: Buy rate (should be lower)

        Raises:
            ValueError: If rates are inconsistent
        """
        # Buy rate must be lower than sell rate
        if compra >= venta:
            raise ValueError(
                f"Buy rate {compra} must be less than sell rate {venta}"
            )

        # Check spread is reasonable
        spread = venta - compra
        if spread < self.MIN_SPREAD:
            logger.warning(
                f"Unusually small spread: {spread} BOB "
                f"(venta={venta}, compra={compra})"
            )
        elif spread > self.MAX_SPREAD:
            logger.warning(
                f"Unusually large spread: {spread} BOB "
                f"(venta={venta}, compra={compra})"
            )

    def _get_fallback_rate(self, last_error: Optional[str] = None) -> Dict[str, Any]:
        """
        Get fallback rate from database cache or use emergency fixed rate.

        Strategy:
        1. Try to get most recent rate from database (max 7 days old)
        2. If no cached rate, use known fixed rate (6.96 BOB/USD)

        Args:
            last_error: Error message from failed fetch attempts

        Returns:
            dict with rate data
        """
        from apps.market_data.models import MacroeconomicIndicator

        # Try to get cached rate from database
        try:
            cached = MacroeconomicIndicator.objects.filter(
                official_exchange_rate__isnull=False
            ).order_by('-date').first()

            if cached:
                age_days = (date.today() - cached.date).days

                if age_days > 7:
                    logger.error(
                        f"Cached BCB rate is {age_days} days old (stale)"
                    )
                elif age_days > 3:
                    logger.warning(
                        f"Cached BCB rate is {age_days} days old"
                    )

                logger.info(
                    f"Using cached BCB rate: {cached.official_exchange_rate} "
                    f"from {cached.date}"
                )

                return {
                    'success': True,
                    'rate': cached.official_exchange_rate,
                    'date': cached.date,
                    'source': 'BCB_CACHED',
                    'raw_data': {
                        'cached_from': str(cached.date),
                        'age_days': age_days,
                        'last_error': last_error
                    },
                    'error': None
                }
        except Exception as e:
            logger.error(f"Failed to get cached rate: {e}")

        # Emergency fallback - use known fixed rate
        OFFICIAL_FIXED_RATE = Decimal("6.96")

        logger.warning(
            f"Using emergency fallback rate: {OFFICIAL_FIXED_RATE} BOB/USD"
        )

        return {
            'success': True,
            'rate': OFFICIAL_FIXED_RATE,
            'date': date.today(),
            'source': 'BCB_EMERGENCY_FALLBACK',
            'raw_data': {
                'reason': 'All fetch methods and cache failed',
                'fallback_rate': str(OFFICIAL_FIXED_RATE),
                'note': 'Official fixed rate since 2011',
                'last_error': last_error
            },
            'error': None
        }

    def save_rate(
        self, rate_venta: Decimal, rate_compra: Optional[Decimal] = None
    ) -> Any:
        """
        Save exchange rate to database.

        Args:
            rate_venta: Decimal sell rate (official rate)
            rate_compra: Decimal buy rate (optional)

        Returns:
            MacroeconomicIndicator instance
        """
        from apps.market_data.models import MacroeconomicIndicator

        today = date.today()

        # Get or create record for today
        indicator, created = MacroeconomicIndicator.objects.update_or_create(
            date=today,
            defaults={
                'official_exchange_rate': rate_venta,
                'source': 'BCB',
                'raw_data': {
                    'venta': str(rate_venta),
                    'compra': str(rate_compra) if rate_compra else None,
                    'url': self.BCB_URL,
                    'scraped_at': datetime.now(timezone.utc).isoformat(),
                    'method': 'html_scraping'
                }
            }
        )

        action = 'Created' if created else 'Updated'
        logger.info(f"{action} BCB rate for {today}: {rate_venta} BOB/USD")

        return indicator


# Singleton instance for reuse
_bcb_service = None


def get_bcb_service() -> BCBService:
    """Get or create BCB service singleton."""
    global _bcb_service
    if _bcb_service is None:
        _bcb_service = BCBService()
    return _bcb_service
