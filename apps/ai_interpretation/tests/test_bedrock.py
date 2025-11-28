"""
Comprehensive unit tests for Bedrock client.

Tests BedrockClient with mocked AWS calls.
"""
from unittest.mock import patch, MagicMock

from apps.ai_interpretation.services import BedrockClient
from apps.ai_interpretation.services.cache_manager import InterpretationCache
from apps.ai_interpretation.services.prompt_builder import PromptBuilder


class TestBedrockClient:
    """Tests for BedrockClient class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = BedrockClient()

    def test_generate_inelastic_interpretation(self):
        """Test generating interpretation for inelastic demand."""
        interpretation = self.client.generate_interpretation(
            elasticity_coefficient=-0.65,
            classification='inelastic',
            data_context={'period': '2025-11', 'data_points': 18, 'quality_score': 0.89}
        )

        assert len(interpretation) > 200
        assert 'bolivia' in interpretation.lower()

    def test_generate_elastic_interpretation(self):
        """Test generating interpretation for elastic demand."""
        interpretation = self.client.generate_interpretation(
            elasticity_coefficient=-1.85,
            classification='elastic',
            data_context={'period': '2025-11', 'data_points': 18, 'quality_score': 0.89}
        )

        assert len(interpretation) > 200
        assert 'elastic' in interpretation.lower() or 'elástic' in interpretation.lower()

    def test_generate_unitary_interpretation(self):
        """Test generating interpretation for unitary elasticity."""
        interpretation = self.client.generate_interpretation(
            elasticity_coefficient=-1.0,
            classification='unitary',
            data_context={'period': '2025-11', 'data_points': 18, 'quality_score': 0.89}
        )

        assert len(interpretation) > 100
        assert 'unitar' in interpretation.lower()

    def test_interpretation_includes_context(self):
        """Test that interpretation includes Bolivian context."""
        interpretation = self.client.generate_interpretation(
            elasticity_coefficient=-0.75,
            classification='inelastic',
            data_context={'period': '2025-11', 'data_points': 30, 'quality_score': 0.95}
        )

        assert any(term in interpretation.lower() for term in ['usdt', 'bob', 'bolivian', 'bcb', 'banco central'])

    def test_fallback_interpretation_on_aws_failure(self):
        """Test fallback to rule-based interpretation when AWS fails."""
        with patch.object(self.client, 'client', None):
            interpretation = self.client.generate_interpretation(
                elasticity_coefficient=-0.65,
                classification='inelastic',
                data_context={'period': '2025-11', 'data_points': 18, 'quality_score': 0.89}
            )

        assert len(interpretation) > 100
        assert 'inelástic' in interpretation.lower() or 'inelastic' in interpretation.lower()

    @patch('apps.ai_interpretation.services.bedrock_client.boto3.client')
    def test_aws_client_initialization(self, mock_boto):
        """Test AWS Bedrock client initialization."""
        mock_bedrock = MagicMock()
        mock_boto.return_value = mock_bedrock

        client = BedrockClient()

        assert client is not None

    def test_mock_mode_enabled(self):
        """Test mock mode returns valid interpretation."""
        client = BedrockClient()
        client.mock_mode = True

        interpretation = client.generate_interpretation(
            elasticity_coefficient=-0.65,
            classification='inelastic',
            data_context={'period': '2025-11', 'data_points': 18, 'quality_score': 0.89}
        )

        assert len(interpretation) > 100

    def test_interpretation_coefficient_in_text(self):
        """Test that elasticity coefficient appears in interpretation."""
        interpretation = self.client.generate_interpretation(
            elasticity_coefficient=-0.8734,
            classification='inelastic',
            data_context={'period': '2025-11', 'data_points': 18, 'quality_score': 0.89}
        )

        assert '-0.8734' in interpretation or '0.8734' in interpretation


class TestPromptBuilder:
    """Tests for PromptBuilder class."""

    def test_build_prompt_includes_coefficient(self):
        """Test prompt includes elasticity coefficient."""
        prompt = PromptBuilder.build_elasticity_prompt(
            elasticity=-0.75,
            classification='inelastic',
            context={'period': '2025-11', 'data_points': 20}
        )

        assert '-0.75' in prompt or '0.75' in prompt

    def test_build_prompt_includes_classification(self):
        """Test prompt includes classification."""
        prompt = PromptBuilder.build_elasticity_prompt(
            elasticity=-0.75,
            classification='inelastic',
            context={'period': '2025-11', 'data_points': 20}
        )

        assert 'inelastic' in prompt.lower() or 'inelástic' in prompt.lower()

    def test_build_prompt_spanish_language(self):
        """Test prompt is in Spanish for Bolivian context."""
        prompt = PromptBuilder.build_elasticity_prompt(
            elasticity=-0.75,
            classification='inelastic',
            context={'period': '2025-11', 'data_points': 20}
        )

        assert any(word in prompt.lower() for word in ['elasticidad', 'precio', 'demanda', 'mercado'])


class TestInterpretationCache:
    """Tests for InterpretationCache class."""

    def test_cache_key_generation(self):
        """Test cache key is generated correctly."""
        key = InterpretationCache.get_cache_key(-0.75, 'inelastic', {'method': 'midpoint'})

        assert key is not None
        assert isinstance(key, str)
        assert len(key) > 0

    def test_cache_key_uniqueness(self):
        """Test different inputs generate different keys."""
        key1 = InterpretationCache.get_cache_key(-0.75, 'inelastic', {'method': 'midpoint'})
        key2 = InterpretationCache.get_cache_key(-1.50, 'elastic', {'method': 'regression'})

        assert key1 != key2

    @patch('apps.ai_interpretation.services.cache_manager.cache')
    def test_cache_hit(self, mock_cache):
        """Test cache hit returns cached interpretation."""
        mock_cache.get.return_value = "Cached interpretation text"

        result = InterpretationCache.get(-0.75, 'inelastic', {'method': 'midpoint'})

        assert result == "Cached interpretation text"

    @patch('apps.ai_interpretation.services.cache_manager.cache')
    def test_cache_miss(self, mock_cache):
        """Test cache miss returns None."""
        mock_cache.get.return_value = None

        result = InterpretationCache.get(-0.75, 'inelastic', {'method': 'midpoint'})

        assert result is None

    @patch('apps.ai_interpretation.services.cache_manager.cache')
    def test_cache_set(self, mock_cache):
        """Test setting cache value."""
        InterpretationCache.set(-0.75, 'inelastic', {'method': 'midpoint'}, "New interpretation")

        mock_cache.set.assert_called_once()
