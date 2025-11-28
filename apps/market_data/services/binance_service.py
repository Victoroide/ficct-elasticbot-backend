"""
Binance P2P API integration for USDT/BOB market data.

API Endpoint: https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search
"""
import requests
from typing import Dict, List
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class BinanceP2PService:
    """
    Service for fetching USDT/BOB market data from Binance P2P.

    Binance P2P is the primary source for cryptocurrency prices in Bolivia
    since traditional exchanges are restricted by BCB regulations.
    """

    API_URL = 'https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search'
    TIMEOUT = 10  # seconds
    MAX_RETRIES = 3

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (compatible; ElasticBot/2.0; +https://ficct.com/bot)'
        })

    def fetch_usdt_bob_data(
        self,
        trade_type: str = 'SELL',
        page: int = 1,
        rows: int = 20
    ) -> Dict:
        """
        Fetch USDT/BOB market data from Binance P2P.

        Args:
            trade_type: 'SELL' or 'BUY'
            page: Page number (1-indexed)
            rows: Number of results per page

        Returns:
            Dictionary with:
                - data: List of advertisements
                - total: Total number of ads
                - success: Boolean

        Raises:
            requests.RequestException: If API call fails
        """
        payload = {
            "asset": "USDT",
            "fiat": "BOB",
            "merchantCheck": False,
            "page": page,
            "payTypes": [],
            "publisherType": None,
            "rows": rows,
            "tradeType": trade_type,
            "transAmount": ""
        }

        logger.info(f"Fetching Binance P2P data: {trade_type} USDT/BOB")

        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.session.post(
                    self.API_URL,
                    json=payload,
                    timeout=self.TIMEOUT
                )
                response.raise_for_status()

                data = response.json()

                if not data.get('success'):
                    raise ValueError(f"Binance API returned success=false: {data}")

                logger.info(f"Fetched {len(data['data'])} advertisements")

                return data

            except requests.RequestException as e:
                logger.warning(
                    f"Binance API attempt {attempt + 1}/{self.MAX_RETRIES} failed: {e}"
                )

                if attempt == self.MAX_RETRIES - 1:
                    logger.error("All Binance API retry attempts failed")
                    raise

        raise RuntimeError("Failed to fetch data after retries")

    def calculate_market_snapshot(self) -> Dict:
        """
        Calculate market snapshot from current P2P data.

        Returns:
            Dictionary with aggregated market metrics:
                - average_sell_price: Average USDT sell price in BOB
                - average_buy_price: Average USDT buy price in BOB
                - total_volume: Total USDT available
                - spread_percentage: Bid-ask spread
                - num_active_traders: Number of unique traders
                - raw_data: Raw API responses
        """
        # Fetch sell orders (people selling USDT for BOB)
        sell_data = self.fetch_usdt_bob_data(trade_type='SELL', rows=20)

        # Fetch buy orders (people buying USDT with BOB)
        buy_data = self.fetch_usdt_bob_data(trade_type='BUY', rows=20)

        # Parse sell orders
        sell_ads = sell_data.get('data', [])
        sell_prices = []
        sell_volumes = []
        sell_traders = set()

        for ad in sell_ads:
            adv = ad.get('adv', {})
            price = Decimal(adv.get('price', 0))
            volume = Decimal(adv.get('surplusAmount', 0))
            trader_id = adv.get('advertiserNo')

            if price > 0 and volume > 0:
                sell_prices.append(price)
                sell_volumes.append(volume)
                if trader_id:
                    sell_traders.add(trader_id)

        # Parse buy orders
        buy_ads = buy_data.get('data', [])
        buy_prices = []
        buy_volumes = []
        buy_traders = set()

        for ad in buy_ads:
            adv = ad.get('adv', {})
            price = Decimal(adv.get('price', 0))
            volume = Decimal(adv.get('tradableQuantity', 0))
            trader_id = adv.get('advertiserNo')

            if price > 0 and volume > 0:
                buy_prices.append(price)
                buy_volumes.append(volume)
                if trader_id:
                    buy_traders.add(trader_id)

        # Calculate averages
        avg_sell_price = sum(sell_prices) / len(sell_prices) if sell_prices else Decimal(0)
        avg_buy_price = sum(buy_prices) / len(buy_prices) if buy_prices else Decimal(0)
        total_volume = sum(sell_volumes) + sum(buy_volumes)

        # Calculate spread
        if avg_sell_price > 0 and avg_buy_price > 0:
            spread_pct = ((avg_sell_price - avg_buy_price) / avg_buy_price) * 100
        else:
            spread_pct = Decimal(0)

        # Count unique traders
        all_traders = sell_traders.union(buy_traders)

        logger.info(
            f"Market snapshot: Sell={avg_sell_price:.4f}, Buy={avg_buy_price:.4f}, "
            f"Volume={total_volume:.2f}, Traders={len(all_traders)}"
        )

        return {
            'average_sell_price': float(avg_sell_price),
            'average_buy_price': float(avg_buy_price) if avg_buy_price > 0 else None,
            'total_volume': float(total_volume),
            'spread_percentage': float(spread_pct),
            'num_active_traders': len(all_traders),
            'raw_data': {
                'sell_ads_count': len(sell_ads),
                'buy_ads_count': len(buy_ads),
                'sell_traders': len(sell_traders),
                'buy_traders': len(buy_traders)
            }
        }

    def detect_outliers(self, prices: List[Decimal], threshold: float = 2.0) -> List[bool]:
        """
        Detect price outliers using z-score method.

        Args:
            prices: List of price observations
            threshold: Z-score threshold (default: 2.0 std devs)

        Returns:
            List of booleans indicating outliers
        """
        if len(prices) < 3:
            return [False] * len(prices)

        mean = sum(prices) / len(prices)
        variance = sum((p - mean) ** 2 for p in prices) / len(prices)
        std_dev = variance ** Decimal('0.5')

        if std_dev == 0:
            return [False] * len(prices)

        outliers = []
        for price in prices:
            z_score = abs((price - mean) / std_dev)
            outliers.append(float(z_score) > threshold)

        return outliers
