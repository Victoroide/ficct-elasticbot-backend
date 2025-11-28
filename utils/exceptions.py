from rest_framework.views import exception_handler
from rest_framework.exceptions import APIException
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


class ExternalAPIException(APIException):
    """Exception raised when external API calls fail."""
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'External service temporarily unavailable.'
    default_code = 'external_api_error'


class InsufficientDataException(APIException):
    """Exception raised when there's insufficient data for calculations."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Insufficient data points for calculation.'
    default_code = 'insufficient_data'


class InvalidDataException(APIException):
    """Exception raised when data validation fails."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid data provided.'
    default_code = 'invalid_data'


class CalculationTimeoutException(APIException):
    """Exception raised when calculation exceeds timeout."""
    status_code = status.HTTP_408_REQUEST_TIMEOUT
    default_detail = 'Calculation timed out. Please try with smaller dataset.'
    default_code = 'calculation_timeout'


class LLMServiceException(APIException):
    """Exception raised when LLM service fails."""
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'AI interpretation service temporarily unavailable.'
    default_code = 'llm_service_error'


class OutlierDetectedException(APIException):
    """Exception raised when statistical outliers are detected."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = 'Statistical outliers detected in data.'
    default_code = 'outlier_detected'


def custom_exception_handler(exc, context):
    """
    Custom exception handler for DRF views.

    Adds additional logging and structured error responses.
    """
    response = exception_handler(exc, context)

    if response is not None:
        custom_response_data = {
            'error': True,
            'status_code': response.status_code,
            'detail': response.data.get('detail', str(exc)),
            'error_type': exc.__class__.__name__
        }

        if hasattr(exc, 'default_code'):
            custom_response_data['code'] = exc.default_code

        logger.error(
            f"API Exception: {exc.__class__.__name__}",
            extra={
                'status_code': response.status_code,
                'path': context['request'].path,
                'method': context['request'].method,
                'detail': str(exc)
            }
        )

        response.data = custom_response_data

    return response
