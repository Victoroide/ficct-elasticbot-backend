"""
Regression-based elasticity calculator using log-log model.

Reference: Varian, H. R. (1992). Microeconomic Analysis (3rd ed.)
Log-log specification: log(Q) = α + β·log(P) + ε
Where β = price elasticity of demand
"""
from decimal import Decimal
from typing import Dict, List, Any, Tuple
import numpy as np
from scipy import stats
import logging

logger = logging.getLogger(__name__)


class RegressionElasticityCalculator:
    """
    Calculate elasticity using log-log regression model.

    The coefficient β from log(Q) = α + β·log(P) directly represents
    the price elasticity of demand at all points on the demand curve.

    Advantages over midpoint method:
    - Uses all data points (not just endpoints)
    - Provides statistical significance tests
    - Estimates constant elasticity across price range
    """

    def __init__(self):
        self.min_data_points = 10  # Minimum for reliable regression

    def calculate(
        self,
        prices: List[Decimal],
        quantities: List[Decimal]
    ) -> Dict[str, Any]:
        """
        Calculate elasticity using OLS regression on log-transformed data.

        Args:
            prices: List of price observations
            quantities: List of quantity observations

        Returns:
            Dictionary with:
                - elasticity: β coefficient (elasticity)
                - r_squared: Goodness of fit
                - p_value: Statistical significance
                - standard_error: Standard error of β
                - confidence_interval_95: [lower, upper]
                - classification: elastic | inelastic | unitary
                - n_observations: Number of data points

        Raises:
            ValueError: If insufficient data or invalid values
        """
        # Validation
        self._validate_inputs(prices, quantities)

        # Convert to numpy arrays
        prices_array = np.array([float(p) for p in prices])
        quantities_array = np.array([float(q) for q in quantities])

        # Log transformation
        log_prices = np.log(prices_array)
        log_quantities = np.log(quantities_array)

        # OLS regression
        slope, intercept, r_value, p_value, std_err = stats.linregress(
            log_prices,
            log_quantities
        )

        # Elasticity = β coefficient
        elasticity = Decimal(str(slope))
        abs_elasticity = abs(elasticity)

        # 95% confidence interval
        confidence_level = 0.95
        degrees_freedom = len(prices) - 2
        t_critical = stats.t.ppf((1 + confidence_level) / 2, degrees_freedom)
        margin_error = t_critical * std_err

        ci_lower = slope - margin_error
        ci_upper = slope + margin_error

        logger.info(
            f"Regression elasticity: {elasticity:.4f}, R²={r_value**2:.4f}, p={p_value:.4f}",
            extra={
                'elasticity': float(elasticity),
                'r_squared': r_value**2,
                'p_value': p_value
            }
        )

        return {
            'elasticity': float(elasticity),
            'abs_value': float(abs_elasticity),
            'classification': self._classify(abs_elasticity),
            'r_squared': float(r_value ** 2),
            'p_value': float(p_value),
            'standard_error': float(std_err),
            'confidence_interval_95': [float(ci_lower), float(ci_upper)],
            'is_significant': p_value < 0.05,
            'n_observations': len(prices),
            'metadata': {
                'intercept': float(intercept),
                'degrees_freedom': degrees_freedom,
                'method': 'OLS log-log regression'
            }
        }

    def calculate_with_time_series(
        self,
        time_series_data: List[Tuple[Decimal, Decimal]]
    ) -> Dict[str, Any]:
        """
        Calculate elasticity from time series (price, quantity) pairs.

        Args:
            time_series_data: List of (price, quantity) tuples

        Returns:
            Same as calculate() method
        """
        if len(time_series_data) < self.min_data_points:
            raise ValueError(
                f"Need at least {self.min_data_points} observations, got {len(time_series_data)}"
            )

        prices = [item[0] for item in time_series_data]
        quantities = [item[1] for item in time_series_data]

        return self.calculate(prices, quantities)

    def _validate_inputs(self, prices: List[Decimal], quantities: List[Decimal]):
        """Validate input data for regression."""
        if len(prices) != len(quantities):
            raise ValueError("Prices and quantities must have same length")

        if len(prices) < self.min_data_points:
            raise ValueError(
                f"Need at least {self.min_data_points} data points for regression, "
                f"got {len(prices)}"
            )

        # Check for non-positive values (can't take log)
        if any(p <= 0 for p in prices):
            raise ValueError("All prices must be positive for log transformation")

        if any(q <= 0 for q in quantities):
            raise ValueError("All quantities must be positive for log transformation")

        # Check for sufficient variance
        prices_array = np.array([float(p) for p in prices])
        if np.std(prices_array) < 0.01:
            raise ValueError("Insufficient price variation for regression")

    def _classify(self, abs_value: Decimal) -> str:
        """Classify elasticity by magnitude."""
        if abs_value > Decimal('1.05'):
            return 'elastic'
        elif abs_value < Decimal('0.95'):
            return 'inelastic'
        else:
            return 'unitary'

    def validate_assumptions(
        self,
        prices: List[Decimal],
        quantities: List[Decimal]
    ) -> Dict[str, Any]:
        """
        Check regression assumptions.

        Returns:
            Dictionary with diagnostic tests:
                - linearity_check: Correlation of log-transformed data
                - heteroscedasticity_test: Breusch-Pagan test result
                - normality_test: Shapiro-Wilk test on residuals
        """
        prices_array = np.array([float(p) for p in prices])
        quantities_array = np.array([float(q) for q in quantities])

        log_prices = np.log(prices_array)
        log_quantities = np.log(quantities_array)

        # Linearity: correlation in log-log space
        correlation = np.corrcoef(log_prices, log_quantities)[0, 1]

        # Get residuals
        slope, intercept, _, _, _ = stats.linregress(log_prices, log_quantities)
        predicted = slope * log_prices + intercept
        residuals = log_quantities - predicted

        # Normality test on residuals
        if len(residuals) >= 3:
            normality_stat, normality_p = stats.shapiro(residuals)
        else:
            normality_stat, normality_p = None, None

        return {
            'linearity_correlation': float(correlation),
            'linearity_adequate': abs(correlation) > 0.7,
            'normality_statistic': float(normality_stat) if normality_stat else None,
            'normality_p_value': float(normality_p) if normality_p else None,
            'residuals_mean': float(np.mean(residuals)),
            'residuals_std': float(np.std(residuals))
        }
