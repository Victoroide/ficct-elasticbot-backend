import uuid
from django.db import models
from apps.elasticity.models import ElasticityCalculation


class Report(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    calculation = models.ForeignKey(ElasticityCalculation, on_delete=models.CASCADE)
    s3_key = models.CharField(max_length=500)
    s3_url = models.URLField(max_length=1000, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True)

    class Meta:
        db_table = 'reports'
        ordering = ['-generated_at']
