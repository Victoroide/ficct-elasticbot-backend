"""
Prompt engineering for economic interpretations.
"""
from typing import Dict


class PromptBuilder:
    """
    Builds context-rich prompts for LLM interpretation.
    """

    BOLIVIAN_CONTEXT = """
    **Contexto Económico de Bolivia:**
    - Restricciones de acceso al dólar (BCB Resolución 144/2020)
    - Tipo de cambio oficial fijo: 6.96 BOB/USD desde 2011
    - Inflación mensual típica: 0.5-1.5% (INE)
    - Economía informal: ~60% de transacciones
    - USDT como refugio de valor ante restricciones cambiarias
    """

    @classmethod
    def build_elasticity_prompt(
        cls,
        elasticity: float,
        classification: str,
        context: Dict
    ) -> str:
        """Build comprehensive prompt for elasticity interpretation."""
        return f"""{cls.BOLIVIAN_CONTEXT}

**Resultado del Análisis:**
- Elasticidad precio-demanda: {elasticity:.4f}
- Clasificación: {classification.upper()}
- Período: {context.get('start_date')} a {context.get('end_date')}
- Método: {context.get('method', 'Midpoint')}
- Calidad de datos: {context.get('data_quality', 0.85):.0%}

**Tarea:** Interpreta este resultado en el contexto del mercado boliviano de USDT.
Explica las implicaciones económicas en 250-300 palabras.
"""

    @classmethod
    def build_anomaly_prompt(cls, anomaly_description: str) -> str:
        """Build prompt for explaining market anomalies."""
        return f"""{cls.BOLIVIAN_CONTEXT}

**Anomalía Detectada:**
{anomaly_description}

**Tarea:** Explica posibles causas de esta anomalía en el mercado P2P boliviano.
Considera factores macroeconómicos, regulatorios y de mercado.
"""
