"""
PDF report generator using ReportLab.

Generates professional PDF reports for elasticity analysis results.
"""
from io import BytesIO
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
import logging

logger = logging.getLogger(__name__)


class PDFGenerator:
    """
    Generate professional PDF reports for elasticity analysis.

    Uses ReportLab to create formatted PDF documents with:
    - Header with title and metadata
    - Executive summary
    - Detailed calculation results
    - Statistical analysis
    - Methodology explanation
    """

    def __init__(self):
        """Initialize PDF generator with custom styles."""
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Configure custom paragraph styles."""
        self.styles.add(ParagraphStyle(
            name='Title_Custom',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#1a365d')
        ))

        self.styles.add(ParagraphStyle(
            name='Subtitle',
            parent=self.styles['Normal'],
            fontSize=12,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#4a5568')
        ))

        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceBefore=20,
            spaceAfter=10,
            textColor=colors.HexColor('#2d3748')
        ))

        self.styles.add(ParagraphStyle(
            name='BodyText_Custom',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=12,
            alignment=TA_JUSTIFY,
            leading=14
        ))

    def generate_report(self, calculation) -> BytesIO:
        """
        Generate PDF report for elasticity calculation.

        Args:
            calculation: ElasticityCalculation model instance

        Returns:
            BytesIO buffer containing PDF document
        """
        buffer = BytesIO()

        try:
            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=72
            )

            # Build document content
            story = []

            # Title
            story.append(Paragraph(
                "Elasticity Analysis Report",
                self.styles['Title_Custom']
            ))

            # Subtitle with date
            story.append(Paragraph(
                f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}",
                self.styles['Subtitle']
            ))

            story.append(Spacer(1, 20))

            # Executive Summary
            story.extend(self._build_executive_summary(calculation))

            # Calculation Details
            story.extend(self._build_calculation_details(calculation))

            # Statistical Results
            story.extend(self._build_statistical_results(calculation))

            # Methodology Section
            story.extend(self._build_methodology_section(calculation))

            # Footer
            story.extend(self._build_footer())

            # Build PDF
            doc.build(story)
            buffer.seek(0)

            logger.info(f"Generated PDF report for calculation {calculation.id}")
            return buffer

        except Exception as e:
            logger.error(f"PDF generation failed: {e}", exc_info=True)
            # Return simple text fallback
            return self._generate_fallback_report(calculation)

    def _build_executive_summary(self, calculation) -> list:
        """Build executive summary section."""
        elements = []

        elements.append(Paragraph("Executive Summary", self.styles['SectionHeader']))

        # Summary text
        coef = calculation.elasticity_coefficient
        if coef:
            coef_display = f"{abs(float(coef)):.4f}"
        else:
            coef_display = "N/A"

        summary = f"""The price elasticity analysis for USDT/BOB in the Bolivian P2P market
reveals a <b>{calculation.classification.upper()}</b> demand pattern
with an elasticity coefficient of <b>{coef_display}</b>."""

        if calculation.classification == 'elastic':
            summary += """ This indicates that demand is highly responsive to price changes.
A 1% increase in price leads to a greater than 1% decrease in quantity demanded."""
        elif calculation.classification == 'inelastic':
            summary += """ This indicates that demand is relatively unresponsive to price changes.
A 1% increase in price leads to a less than 1% decrease in quantity demanded."""
        else:
            summary += """ This indicates unitary elasticity where percentage changes in price
result in equal percentage changes in quantity demanded."""

        elements.append(Paragraph(summary, self.styles['BodyText_Custom']))
        elements.append(Spacer(1, 15))

        return elements

    def _build_calculation_details(self, calculation) -> list:
        """Build calculation details table."""
        elements = []

        elements.append(Paragraph("Calculation Details", self.styles['SectionHeader']))

        # Details table
        data = [
            ['Parameter', 'Value'],
            ['Calculation ID', str(calculation.id)[:8] + '...'],
            ['Method', calculation.get_method_display()],
            ['Status', calculation.status.upper()],
            ['Date Range', f"{calculation.start_date} to {calculation.end_date}"],
            ['Window Size', f"{calculation.window_size} days"],
            ['Client IP', calculation.client_ip or 'N/A'],
            ['Created', calculation.created_at.strftime('%Y-%m-%d %H:%M:%S')],
        ]

        table = Table(data, colWidths=[2.5 * inch, 3.5 * inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2d3748')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f7fafc')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#2d3748')),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 20))

        return elements

    def _build_statistical_results(self, calculation) -> list:
        """Build statistical results section."""
        elements = []

        elements.append(Paragraph("Statistical Results", self.styles['SectionHeader']))

        # Format values safely
        def fmt(val, decimals=4):
            if val is None:
                return 'N/A'
            return f"{float(val):.{decimals}f}"

        # Results table
        data = [
            ['Metric', 'Value', 'Interpretation'],
            [
                'Elasticity Coefficient',
                fmt(calculation.elasticity_coefficient),
                self._interpret_coefficient(calculation.elasticity_coefficient)
            ],
            [
                'Classification',
                calculation.classification.title(),
                self._interpret_classification(calculation.classification)
            ],
        ]

        # Add method-specific metrics
        if calculation.method == 'regression':
            data.extend([
                [
                    'R-squared',
                    fmt(calculation.r_squared),
                    self._interpret_r_squared(calculation.r_squared)
                ],
                [
                    'P-value',
                    fmt(calculation.p_value),
                    self._interpret_p_value(calculation.p_value)
                ],
                [
                    'Confidence Interval',
                    f"[{fmt(calculation.confidence_interval_lower)}, "
                    f"{fmt(calculation.confidence_interval_upper)}]",
                    '95% CI'
                ],
            ])

        table = Table(data, colWidths=[1.8 * inch, 1.5 * inch, 2.7 * inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a365d')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#2d3748')),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e0')),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 20))

        return elements

    def _build_methodology_section(self, calculation) -> list:
        """Build methodology explanation section."""
        elements = []

        elements.append(Paragraph("Methodology", self.styles['SectionHeader']))

        if calculation.method == 'midpoint':
            method_text = """<b>Midpoint Arc Elasticity Method</b><br/><br/>
This calculation uses the arc elasticity formula (Mankiw, 2020), which
calculates elasticity using the midpoint between two price-quantity pairs:
<br/><br/>
E = [(Q2 - Q1) / ((Q2 + Q1) / 2)] / [(P2 - P1) / ((P2 + P1) / 2)]
<br/><br/>
This method provides a symmetric measure that gives the same result
regardless of the direction of price change."""
        else:
            method_text = """<b>Log-Log Regression Method</b><br/><br/>
This calculation uses Ordinary Least Squares (OLS) regression on
log-transformed price and quantity data:
<br/><br/>
ln(Q) = alpha + beta * ln(P) + epsilon
<br/><br/>
The coefficient beta directly represents the price elasticity of demand.
This method provides statistical measures including R-squared, p-values,
and confidence intervals for robust inference."""

        elements.append(Paragraph(method_text, self.styles['BodyText_Custom']))
        elements.append(Spacer(1, 15))

        return elements

    def _build_footer(self) -> list:
        """Build report footer."""
        elements = []

        elements.append(Spacer(1, 30))

        footer_style = ParagraphStyle(
            name='Footer',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#718096'),
            alignment=TA_CENTER
        )

        elements.append(Paragraph(
            "Generated by ElasticBot API v2.0",
            footer_style
        ))
        elements.append(Paragraph(
            "USDT/BOB Price Elasticity Analysis System",
            footer_style
        ))

        return elements

    def _interpret_coefficient(self, coef) -> str:
        """Interpret elasticity coefficient value."""
        if coef is None:
            return 'No data'
        abs_coef = abs(float(coef))
        if abs_coef > 1:
            return 'Demand is elastic'
        elif abs_coef < 1:
            return 'Demand is inelastic'
        return 'Unitary elasticity'

    def _interpret_classification(self, classification: str) -> str:
        """Interpret classification."""
        interpretations = {
            'elastic': '|E| > 1: High price sensitivity',
            'inelastic': '|E| < 1: Low price sensitivity',
            'unitary': '|E| = 1: Proportional response',
        }
        return interpretations.get(classification, 'Unknown')

    def _interpret_r_squared(self, r_squared) -> str:
        """Interpret R-squared value."""
        if r_squared is None:
            return 'N/A'
        r2 = float(r_squared)
        if r2 >= 0.9:
            return 'Excellent fit'
        elif r2 >= 0.7:
            return 'Good fit'
        elif r2 >= 0.5:
            return 'Moderate fit'
        return 'Poor fit'

    def _interpret_p_value(self, p_value) -> str:
        """Interpret p-value for statistical significance."""
        if p_value is None:
            return 'N/A'
        p = float(p_value)
        if p < 0.01:
            return 'Highly significant'
        elif p < 0.05:
            return 'Significant'
        elif p < 0.10:
            return 'Marginally significant'
        return 'Not significant'

    def _generate_fallback_report(self, calculation) -> BytesIO:
        """Generate simple text report as fallback."""
        buffer = BytesIO()
        content = f"""ELASTICBOT ELASTICITY ANALYSIS REPORT
{'=' * 50}

Calculation ID: {calculation.id}
Method: {calculation.method}
Elasticity Coefficient: {calculation.elasticity_coefficient}
Classification: {calculation.classification}
Status: {calculation.status}

Date Range: {calculation.start_date} to {calculation.end_date}
Window Size: {calculation.window_size} days

Generated: {datetime.now().isoformat()}

---
ElasticBot API v2.0
USDT/BOB Price Elasticity Analysis System
"""
        buffer.write(content.encode('utf-8'))
        buffer.seek(0)
        return buffer
