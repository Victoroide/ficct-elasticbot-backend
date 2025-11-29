"""
AWS Bedrock integration for economic interpretation.

Redesigned to produce clean, plain-text interpretations without markdown or code artifacts.
"""
import json
import logging
import re
from typing import Dict
from django.conf import settings

logger = logging.getLogger(__name__)

try:
    import boto3
    from botocore.exceptions import ClientError, BotoCoreError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    logger.warning("boto3 not installed - using mock Bedrock responses")


class BedrockClient:
    """
    AWS Bedrock client for LLM-powered economic interpretations.

    Produces clean, plain-text Spanish interpretations without markdown or code.
    """

    MODEL_ID = "us.meta.llama4-maverick-17b-instruct-v1:0"
    MAX_TOKENS = 400  # Reduced to prevent overly long responses
    TEMPERATURE = 0.3  # Lower temperature for more consistent output

    # Fixed system prompt for consistent behavior
    SYSTEM_PROMPT = """Eres un economista que analiza resultados de elasticidad precio de la demanda para el mercado P2P de USDT/BOB en Bolivia. Debes escribir interpretaciones breves, claras y rigurosas en español, en uno o dos párrafos, usando solo texto plano (sin código, sin listas, sin markdown). No expliques cómo se implementa el cálculo, ni muestres código, ni describas pasos internos. No inventes datos adicionales: usa únicamente la información numérica y contextual que se te proporciona."""

    def __init__(self):
        self.client = None
        self.mock_mode = False

        if BOTO3_AVAILABLE:
            try:
                self.client = boto3.client(
                    service_name='bedrock-runtime',
                    region_name=getattr(settings, 'AWS_BEDROCK_REGION', 'us-east-1'),
                    aws_access_key_id=getattr(settings, 'AWS_ACCESS_KEY_ID', None),
                    aws_secret_access_key=getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
                )
                logger.info("AWS Bedrock client initialized successfully")
            except Exception as e:
                logger.warning(f"Could not initialize Bedrock client: {e}. Using mock mode.")
                self.mock_mode = True
        else:
            self.mock_mode = True

    def generate_interpretation(
        self,
        elasticity_coefficient: float,
        classification: str,
        data_context: Dict
    ) -> str:
        """
        Generate clean economic interpretation of elasticity result.

        Args:
            elasticity_coefficient: Calculated elasticity value
            classification: elastic | inelastic | unitary
            data_context: Additional context (period, data quality, etc.)

        Returns:
            Spanish-language plain text interpretation (1-3 paragraphs)
        """
        if self.mock_mode or not self.client:
            return self._generate_mock_interpretation(
                elasticity_coefficient,
                classification,
                data_context
            )

        try:
            user_prompt = self._build_user_prompt(
                elasticity_coefficient,
                classification,
                data_context
            )

            # Use proper Llama 4 format with system and user prompts
            request_body = {
                "messages": [
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": self.MAX_TOKENS,
                "temperature": self.TEMPERATURE,
                "top_p": 0.9
            }

            response = self.client.invoke_model(
                modelId=self.MODEL_ID,
                body=json.dumps(request_body)
            )

            response_body = json.loads(response['body'].read())
            interpretation = response_body.get('choices', [{}])[0].get('message', {}).get('content', '')

            # Post-process to ensure clean output
            interpretation = self._sanitize_output(interpretation)

            logger.info(
                f"Generated interpretation via Bedrock: {len(interpretation)} chars",
                extra={'elasticity': elasticity_coefficient, 'classification': classification}
            )

            return interpretation

        except (ClientError, BotoCoreError) as e:
            logger.error(f"Bedrock API error: {e}")
            return self._generate_mock_interpretation(
                elasticity_coefficient,
                classification,
                data_context
            )
        except Exception as e:
            logger.error(f"Unexpected error generating interpretation: {e}")
            return self._generate_mock_interpretation(
                elasticity_coefficient,
                classification,
                data_context
            )

    def _sanitize_output(self, text: str) -> str:
        """
        Remove markdown, code blocks, and meta-commentary from LLM output.
        """
        if not text:
            return "No se pudo generar interpretación con los datos actuales."

        # Remove code blocks
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)

        # Remove markdown headers
        text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)

        # Remove bullet points and numbered lists
        text = re.sub(r'^\s*[-*]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)

        # Remove backticks
        text = text.replace('`', '')

        # Cut off at meta-commentary patterns
        meta_patterns = [
            r'El código.*?define',
            r'La función.*?genera',
            r'Here is.*?implementation',
            r'This code.*?does',
            r'La implementación.*?sigue',
            r'Para generar.*?usamos'
        ]

        for pattern in meta_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                text = text[:match.start()]

        # Clean up whitespace
        text = text.strip()

        # Limit length
        if len(text) > 800:
            text = text[:797] + '...'

        # If after sanitization we have empty or meta-text, return fallback
        if len(text) < 20 or any(pattern in text.lower() for pattern in ['código', 'función', 'implementation', 'define']):
            return "No se pudo generar interpretación válida con los datos actuales. Revise manualmente los resultados numéricos."

        return text

    def _build_user_prompt(
        self,
        elasticity: float,
        classification: str,
        context: Dict
    ) -> str:
        """Build clean user prompt with calculation context."""
        # Extract context values
        method = context.get('method', 'Punto Medio')
        period = context.get('period', 'última semana')
        data_points = context.get('data_points', 50)
        start_date = context.get('start_date', 'fecha de inicio')
        end_date = context.get('end_date', 'fecha final')
        
        # Check reliability from metadata if available
        reliability_info = context.get('reliability', {})
        is_reliable = reliability_info.get('is_reliable', True)
        
        # Build clean user prompt
        prompt = f"""Contexto del cálculo de elasticidad:
- Coeficiente de elasticidad: {elasticity:.2f}
- Clasificación: {classification.upper()}
- Método: {method}
- Periodo analizado: desde {start_date} hasta {end_date}
- Ventana de agregación: por día
- Puntos de datos usados: {data_points}
- Contexto: mercado P2P de USDT/BOB en Bolivia, donde el USDT se usa como refugio de valor frente a la inflación y restricciones cambiarias
{'- Nota: el cálculo fue marcado como de baja confiabilidad por poca variación en el precio o en la cantidad. Menciona esta cautela en tu interpretación.' if not is_reliable else ''}

A partir de estos datos, escribe una interpretación breve en español (1-3 párrafos) que explique:
1) Qué significa este valor de elasticidad para la sensibilidad de la demanda frente a cambios de precio.
2) Qué implicaciones prácticas tiene para personas que usan USDT en Bolivia.

Usa solo texto plano. No uses markdown, no muestres código, no expliques cómo se implementa la función ni hables del modelo de lenguaje."""

        return prompt

    def _generate_mock_interpretation(
        self,
        elasticity: float,
        classification: str,
        context: Dict
    ) -> str:
        """
        Generate clean rule-based interpretation when Bedrock unavailable.
        Returns plain text without markdown or code artifacts.
        """
        abs_e = abs(elasticity)
        data_points = context.get('data_points', 50)
        method = context.get('method', 'Punto Medio')
        period = context.get('period', 'periodo analizado')
        
        # Check if result is reliable
        is_unreliable = abs_e > 10

        if is_unreliable:
            interpretation = f"""El coeficiente de {elasticity:.2f} es inusualmente alto y debe interpretarse con cautela. Esto puede deberse a que el precio del USDT/BOB varió muy poco durante el periodo analizado, mientras que el volumen ofertado fluctuó por factores no relacionados con el precio. En el mercado boliviano, el USDT funciona como refugio de valor ante las restricciones cambiarias, por lo que pequeñas variaciones de precio pueden producir coeficientes extremos que no reflejan el comportamiento real de la demanda. Para obtener resultados más confiables, seleccione un periodo con mayor variación de precios o utilice el método de Regresión con más datos históricos."""

        elif classification.lower() == 'inelastic':
            interpretation = f"""El coeficiente de {elasticity:.2f} indica demanda inelástica: los cambios en el precio del USDT generan cambios proporcionalmente menores en la cantidad demandada. En Bolivia, esto confirma que el USDT funciona como bien de necesidad, ya que las restricciones de acceso al dólar hacen que los usuarios mantengan su demanda incluso cuando el precio sube al no tener alternativas viables para proteger sus ahorros. La implicación práctica es que el mercado P2P es estable, con vendedores que pueden confiar en demanda consistente y compradores que encontrarán disponibilidad aunque el precio fluctúe."""

        elif classification.lower() == 'elastic':
            interpretation = f"""El coeficiente de {elasticity:.2f} indica demanda elástica: los cambios en el precio del USDT generan cambios proporcionalmente mayores en la cantidad demandada. Este comportamiento es atípico para el USDT en Bolivia, donde normalmente actúa como refugio de valor con demanda estable. Una elasticidad alta puede indicar un periodo de incertidumbre económica, disponibilidad temporal de alternativas al USDT, o actividad especulativa elevada. La implicación práctica es mayor volatilidad en el mercado P2P, con precios que pueden ajustarse rápidamente y oportunidades de arbitraje, pero también mayor riesgo."""

        else:  # unitary
            interpretation = f"""El coeficiente de {elasticity:.2f} indica demanda unitaria: los cambios en precio y cantidad son proporcionales. Esto sugiere un mercado en equilibrio donde coexisten usuarios que necesitan USDT independientemente del precio (ahorristas) y usuarios sensibles al precio (traders), un comportamiento típico de mercados maduros. La implicación práctica es que el mercado P2P boliviano muestra estabilidad, con ingresos totales de los vendedores que se mantienen relativamente constantes aunque el precio varíe."""

        return interpretation
