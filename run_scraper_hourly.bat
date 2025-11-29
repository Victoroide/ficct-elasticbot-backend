@echo off
REM Simple Windows batch script to run scraper every hour
REM This is a fallback solution when Celery is not working

echo Starting Binance P2P Scraper - Hourly Scheduler
echo ================================================

:loop
    echo.
    echo [%date% %time%] Running scraper...
    
    REM Run the Django management command
    cd /d "d:\Repositories\python\django\ficct-elasticbot-backend"
    python manage.py run_scraper
    
    echo.
    echo [%date% %time%] Scraper execution completed. Waiting 1 hour...
    
    REM Wait for 1 hour (3600 seconds)
    timeout /t 3600 /nobreak
    
    REM Loop back to run again
    goto loop
