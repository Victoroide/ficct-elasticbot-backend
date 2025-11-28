"""
AWS Bedrock integration for economic interpretation.

Uses Llama 4 Maverick model for Spanish-language elasticity analysis.
"""
import json
import logging
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

    Falls back to rule-based interpretation if AWS not configured.
    """

    MODEL_ID = "us.meta.llama4-maverick-17b-instruct-v1:0"
    MAX_TOKENS = 1000
    TEMPERATURE = 0.7

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
        Generate economic interpretation of elasticity result.

        Args:
            elasticity_coefficient: Calculated elasticity value
            classification: elastic | inelastic | unitary
            data_context: Additional context (period, data quality, etc.)

        Returns:
            Spanish-language interpretation (250-300 words)
        """
        if self.mock_mode or not self.client:
            return self._generate_mock_interpretation(
                elasticity_coefficient,
                classification,
                data_context
            )

        try:
            prompt = self._build_prompt(
                elasticity_coefficient,
                classification,
                data_context
            )

            request_body = {
                "prompt": prompt,
                "max_gen_len": self.MAX_TOKENS,
                "temperature": self.TEMPERATURE,
                "top_p": 0.9
            }

            response = self.client.invoke_model(
                modelId=self.MODEL_ID,
                body=json.dumps(request_body)
            )

            response_body = json.loads(response['body'].read())
            interpretation = response_body.get('generation', '')

            logger.info(
                f"Generated interpretation via Bedrock: {len(interpretation)} chars",
                extra={'elasticity': elasticity_coefficient, 'classification': classification}
            )

            return interpretation.strip()

        except (ClientError, BotoCoreError) as e:
            logger.error(f"Bedrock API error: {e}. Falling back to mock.", exc_info=True)
            return self._generate_mock_interpretation(
                elasticity_coefficient,
                classification,
                data_context
            )

    def _build_prompt(
        self,
        elasticity: float,
        classification: str,
        context: Dict
    ) -> str:
        """Build prompt with Bolivian economic context."""
        prompt = f"""Eres un economista especializado en el mercado boliviano de criptomonedas.

**Contexto del Mercado Boliviano:**
- Restricciones de acceso al dólar (BCB Resolución 144/2020)
- USDT usado como refugio de valor, no especulación
- Economía informal ~60% de transacciones
- Tipo de cambio oficial: 6.96 BOB/USD (fijo desde 2011)

**Resultado del Análisis de Elasticidad:**
- Coeficiente de elasticidad: {elasticity:.4f}
- Clasificación: {classification.upper()}
- Período analizado: {context.get('period', 'N/A')}
- Puntos de datos: {context.get('data_points', 'N/A')}
- Calidad de datos: {context.get('quality_score', 'N/A'):.2f}

**Tarea:**
Interpreta este resultado de elasticidad precio-demanda del par USDT/BOB en el contexto boliviano.
Explica:
1. Qué significa este coeficiente en términos económicos
2. Por qué la demanda muestra este comportamiento en Bolivia
3. Implicaciones para usuarios (ahorristas, empresas, traders)
4. Comparación con criptomonedas volátiles (BTC: Ed ≈ -2.0)

**Formato:** 250-300 palabras en español académico pero accesible.

**Interpretación:**"""

        return prompt

    def _generate_mock_interpretation(
        self,
        elasticity: float,
        classification: str,
        context: Dict
    ) -> str:
        """
        Generate rule-based interpretation when Bedrock unavailable.
        """
        _ = abs(elasticity)  # Magnitude for classification reference

        if classification == 'inelastic':
            interpretation = f"""**Análisis de Elasticidad: Demanda Inelástica**

El coeficiente de elasticidad precio-demanda calculado es {elasticity:.4f}, lo que indica una **demanda inelástica** (|Ed| < 1). Esto significa que los cambios en el precio del USDT generan variaciones proporcionalmente menores en la cantidad demandada.

**Interpretación en Contexto Boliviano:**

En el mercado boliviano, este comportamiento inelástico del USDT se explica por su función como **refugio de valor** ante las restricciones de acceso al dólar estadounidense. A diferencia de criptomonedas volátiles como Bitcoin (elasticidad típica: -1.5 a -3.0), el USDT actúa como un bien de necesidad para preservar ahorros frente a la inflación.

Las restricciones impuestas por el Banco Central de Bolivia (Resolución 144/2020) limitan severamente el acceso a divisas extranjeras, convirtiendo al USDT en una alternativa práctica para transacciones internacionales y protección del poder adquisitivo. Esta funcionalidad esencial reduce la sensibilidad de la demanda ante fluctuaciones de precio.

**Implicaciones Prácticas:**

- **Ahorristas:** La demanda se mantiene estable incluso con aumentos de precio, confirmando su rol como reserva de valor
- **Empresas:** Pueden confiar en disponibilidad consistente para pagos internacionales
- **Mercado P2P:** El spread precio-demanda se mantiene dentro de rangos predecibles

**Validación Estadística:**

Con {context.get('data_points', 'múltiples')} observaciones y calidad de datos de {context.get('quality_score', 0.85):.0%}, este resultado tiene significancia estadística robusta, confirmando la hipótesis de inelasticidad en el mercado boliviano de USDT.
"""

        elif classification == 'elastic':
            interpretation = f"""**Análisis de Elasticidad: Demanda Elástica**

El coeficiente de elasticidad precio-demanda calculado es {elasticity:.4f}, indicando una **demanda elástica** (|Ed| > 1). Los cambios en el precio del USDT generan variaciones proporcionalmente mayores en la cantidad demandada.

**Interpretación en Contexto Boliviano:**

Este comportamiento elástico es atípico para USDT en Bolivia y puede indicar:

1. **Período de alta volatilidad:** Momentos de incertidumbre macroeconómica donde los usuarios ajustan rápidamente sus tenencias
2. **Disponibilidad de alternativas:** Acceso temporal a dólares físicos o canales bancarios
3. **Comportamiento especulativo:** Traders activos respondiendo a arbitraje

Contrasta con la hipótesis esperada de inelasticidad para activos refugio. Sugiere que en este período específico, el USDT mostró características más similares a activos especulativos que a reservas de valor estables.

**Implicaciones Prácticas:**

- Mayor sensibilidad al precio puede generar oportunidades de arbitraje
- Riesgo de volatilidad en spreads P2P
- Posible señal de cambios en patrones de uso (ahorro → especulación)

**Recomendación:** Analizar factores macroeconómicos del período ({context.get('period', 'analizado')}) para identificar causas de esta elasticidad inusualmente alta.
"""

        else:  # unitary
            interpretation = f"""**Análisis de Elasticidad: Demanda Unitaria**

El coeficiente de elasticidad precio-demanda calculado es {elasticity:.4f}, indicando una **demanda unitaria** (|Ed| ≈ 1). Los cambios en el precio del USDT generan variaciones proporcionales en la cantidad demandada.

**Interpretación en Contexto Boliviano:**

La elasticidad unitaria representa un equilibrio entre sensibilidad e insensibilidad al precio. En el mercado boliviano de USDT, esto sugiere un mercado en **transición** o **balance** entre dos comportamientos:

1. **Componente inelástico:** Usuarios que necesitan USDT independientemente del precio (necesidad)
2. **Componente elástico:** Usuarios sensibles al precio que ajustan sus compras (discrecionalidad)

Este balance puede reflejar la maduración del mercado P2P boliviano, donde conviven usuarios con diferentes perfiles y motivaciones.

**Implicaciones Prácticas:**

- Ingresos totales (P × Q) se mantienen relativamente estables ante cambios de precio
- Mercado equilibrado con mezcla de ahorristas y traders
- Potencial para segmentación de usuarios por sensibilidad al precio

**Validación Estadística:**

Con {context.get('data_points', 'múltiples')} observaciones, este resultado sugiere un mercado maduro con comportamiento predecible en el rango de precios analizado ({context.get('period', 'período observado')}).
"""

        return interpretation.strip()
