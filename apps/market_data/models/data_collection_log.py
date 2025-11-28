"""
DataCollectionLog model for monitoring data collection tasks.

Tracks all automated data collection attempts for debugging and monitoring.
"""
from django.db import models


class DataCollectionLog(models.Model):
    """
    Logs all data collection attempts for monitoring and debugging.

    Tracks successes, failures, and performance metrics for:
    - Binance P2P API calls
    - BCB exchange rate scraping
    - INE inflation data scraping
    """

    STATUS_CHOICES = [
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('PARTIAL', 'Partial Success'),
    ]

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    source = models.CharField(max_length=50, help_text="Data source name")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    records_created = models.IntegerField(default=0)
    error_message = models.TextField(null=True, blank=True)
    execution_time_ms = models.IntegerField(help_text="Execution time in milliseconds")

    class Meta:
        db_table = 'data_collection_logs'
        ordering = ['-timestamp']
        verbose_name = 'Data Collection Log'
        verbose_name_plural = 'Data Collection Logs'

    def __str__(self):
        return f"{self.source} - {self.status} - {self.timestamp}"
