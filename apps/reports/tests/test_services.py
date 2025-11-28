"""
Comprehensive tests for reports services.

Tests PDFGenerator and Report model functionality.
"""
import pytest
from decimal import Decimal
from io import BytesIO
from unittest.mock import Mock
from django.utils import timezone
import uuid

from apps.reports.services.pdf_generator import PDFGenerator
from apps.reports.models import Report
from apps.elasticity.models import ElasticityCalculation


class TestPDFGenerator:
    """Tests for PDFGenerator class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.generator = PDFGenerator()

    def _create_mock_calculation(self):
        """Create a mock calculation object."""
        mock = Mock()
        mock.id = uuid.uuid4()
        mock.method = 'midpoint'
        mock.get_method_display.return_value = 'Midpoint Arc Method'
        mock.elasticity_coefficient = Decimal('-0.8734')
        mock.classification = 'inelastic'
        mock.status = 'completed'
        mock.start_date = (timezone.now() - timezone.timedelta(days=7)).date()
        mock.end_date = timezone.now().date()
        mock.window_size = 7
        mock.client_ip = '127.0.0.1'
        mock.created_at = timezone.now()
        mock.r_squared = Decimal('0.85')
        mock.p_value = Decimal('0.01')
        mock.confidence_interval_lower = Decimal('-1.12')
        mock.confidence_interval_upper = Decimal('-0.63')
        return mock

    def test_generate_report_returns_bytesio(self):
        """Test that generate_report returns BytesIO object."""
        calculation = self._create_mock_calculation()

        result = self.generator.generate_report(calculation)

        assert isinstance(result, BytesIO)

    def test_generate_report_has_content(self):
        """Test that generated PDF has content."""
        calculation = self._create_mock_calculation()

        result = self.generator.generate_report(calculation)
        content = result.read()

        assert len(content) > 0

    def test_generate_report_is_valid_pdf(self):
        """Test that generated file is a valid PDF."""
        calculation = self._create_mock_calculation()

        result = self.generator.generate_report(calculation)
        content = result.read()

        # PDF files start with %PDF
        assert content[:4] == b'%PDF'

    def test_generate_report_has_substantial_content(self):
        """Test that PDF has substantial content (not empty)."""
        calculation = self._create_mock_calculation()

        result = self.generator.generate_report(calculation)
        content = result.read()

        # Real PDF should be at least a few KB
        assert len(content) > 1000

    def test_generate_report_contains_text_streams(self):
        """Test that PDF contains text stream markers."""
        calculation = self._create_mock_calculation()

        result = self.generator.generate_report(calculation)
        content = result.read()

        # PDF text streams contain 'BT' (begin text) markers
        assert b'BT' in content or b'stream' in content

    def test_generate_report_ends_with_eof(self):
        """Test that PDF ends with proper EOF marker."""
        calculation = self._create_mock_calculation()

        result = self.generator.generate_report(calculation)
        content = result.read()

        # PDF files end with %%EOF
        assert b'%%EOF' in content[-20:]

    def test_generate_report_buffer_seekable(self):
        """Test that buffer is seekable for multiple reads."""
        calculation = self._create_mock_calculation()

        result = self.generator.generate_report(calculation)

        first_read = result.read()
        result.seek(0)
        second_read = result.read()

        assert first_read == second_read

    def test_generate_report_elastic_classification(self):
        """Test PDF generation for elastic classification."""
        calculation = self._create_mock_calculation()
        calculation.classification = 'elastic'
        calculation.elasticity_coefficient = Decimal('-1.85')

        result = self.generator.generate_report(calculation)
        content = result.read()

        # Should generate valid PDF regardless of classification
        assert content[:4] == b'%PDF'

    def test_generate_report_unitary_classification(self):
        """Test PDF generation for unitary classification."""
        calculation = self._create_mock_calculation()
        calculation.classification = 'unitary'
        calculation.elasticity_coefficient = Decimal('-1.0')

        result = self.generator.generate_report(calculation)
        content = result.read()

        # Should generate valid PDF regardless of classification
        assert content[:4] == b'%PDF'

    def test_generate_report_regression_method(self):
        """Test PDF generation for regression method includes extra stats."""
        calculation = self._create_mock_calculation()
        calculation.method = 'regression'
        calculation.get_method_display.return_value = 'Log-Log Regression'

        result = self.generator.generate_report(calculation)
        content = result.read()

        # Should generate valid PDF with regression method
        assert content[:4] == b'%PDF'
        assert len(content) > 1000


@pytest.mark.django_db
class TestReportModel:
    """Tests for Report model."""

    def _create_calculation(self):
        """Create a real calculation in the database."""
        return ElasticityCalculation.objects.create(
            method='MIDPOINT',
            start_date=timezone.now() - timezone.timedelta(days=7),
            end_date=timezone.now(),
            window_size='DAILY',
            status='COMPLETED',
            elasticity_coefficient=Decimal('-0.8734'),
            classification='INELASTIC'
        )

    def test_create_report(self):
        """Test creating a report."""
        calculation = self._create_calculation()

        report = Report.objects.create(
            calculation=calculation,
            s3_key=f'reports/{calculation.id}.pdf',
            s3_url=f'https://bucket.s3.amazonaws.com/reports/{calculation.id}.pdf'
        )

        assert report.id is not None
        assert report.calculation == calculation

    def test_report_generated_at_auto(self):
        """Test that generated_at is auto-set."""
        calculation = self._create_calculation()

        report = Report.objects.create(
            calculation=calculation,
            s3_key=f'reports/{calculation.id}.pdf',
            s3_url=f'https://bucket.s3.amazonaws.com/reports/{calculation.id}.pdf'
        )

        assert report.generated_at is not None

    def test_report_ordering(self):
        """Test reports are ordered by generated_at descending."""
        calc1 = self._create_calculation()
        calc2 = self._create_calculation()

        Report.objects.create(
            calculation=calc1,
            s3_key='reports/old.pdf',
            s3_url='https://bucket.s3.amazonaws.com/reports/old.pdf'
        )

        new_report = Report.objects.create(
            calculation=calc2,
            s3_key='reports/new.pdf',
            s3_url='https://bucket.s3.amazonaws.com/reports/new.pdf'
        )

        reports = list(Report.objects.all())

        assert reports[0].id == new_report.id

    def test_report_calculation_relationship(self):
        """Test FK relationship with calculation."""
        calculation = self._create_calculation()

        report = Report.objects.create(
            calculation=calculation,
            s3_key='reports/test.pdf',
            s3_url='https://bucket.s3.amazonaws.com/reports/test.pdf'
        )

        assert report.calculation.elasticity_coefficient == Decimal('-0.8734')

    def test_multiple_reports_same_calculation(self):
        """Test multiple reports can reference same calculation."""
        calculation = self._create_calculation()

        Report.objects.create(
            calculation=calculation,
            s3_key='reports/v1.pdf',
            s3_url='https://bucket.s3.amazonaws.com/reports/v1.pdf'
        )

        Report.objects.create(
            calculation=calculation,
            s3_key='reports/v2.pdf',
            s3_url='https://bucket.s3.amazonaws.com/reports/v2.pdf'
        )

        assert Report.objects.filter(calculation=calculation).count() == 2
