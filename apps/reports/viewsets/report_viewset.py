from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.http import HttpResponse
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from apps.elasticity.models import ElasticityCalculation
from apps.reports.services import PDFGenerator


class ReportViewSet(viewsets.ViewSet):
    """
    API endpoints for PDF report generation.

    Generates professional PDF reports for completed elasticity calculations.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Report Generation'],
        summary='Download PDF report',
        description='Generate and download a PDF report for a completed elasticity '
                    'calculation. Includes calculation details, methodology, and results.',
        parameters=[
            OpenApiParameter(
                name='pk',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                description='UUID of the elasticity calculation',
            ),
        ],
        responses={
            200: {
                'content': {'application/pdf': {}},
                'description': 'PDF file download',
            },
            400: {'description': 'Calculation not complete'},
            404: {'description': 'Calculation not found'},
        },
    )
    @action(methods=['get'], detail=True, url_path='pdf')
    def pdf(self, request, pk=None):
        """Generate and download PDF report for calculation."""
        try:
            calculation = ElasticityCalculation.objects.get(id=pk)
        except ElasticityCalculation.DoesNotExist:
            return Response({'error': 'Calculation not found'}, status=404)

        if not calculation.is_complete:
            return Response({'error': 'Calculation not complete'}, status=400)

        generator = PDFGenerator()
        pdf_buffer = generator.generate_report(calculation)

        response = HttpResponse(
            pdf_buffer.getvalue(),
            content_type='application/pdf'
        )
        response['Content-Disposition'] = (
            f'attachment; filename="elasticity_{pk}.pdf"'
        )
        return response
