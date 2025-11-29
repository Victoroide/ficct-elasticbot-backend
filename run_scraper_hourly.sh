#!/bin/bash
# Simple Linux/macOS script to run scraper every hour
# This is a fallback solution when Celery is not working

echo "Starting Binance P2P Scraper - Hourly Scheduler"
echo "================================================"

while true; do
    echo ""
    echo "[$(date)] Running scraper..."
    
    # Run the Django management command
    cd "$(dirname "$0")"
    python manage.py run_scraper
    
    echo ""
    echo "[$(date)] Scraper execution completed. Waiting 1 hour..."
    
    # Wait for 1 hour (3600 seconds)
    sleep 3600
done
