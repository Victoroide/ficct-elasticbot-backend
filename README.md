# ElasticBot V2.0: USDT/BOB Elasticity Analysis System

[![Django](https://img.shields.io/badge/Django-5.2-green.svg)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/DRF-3.16-blue.svg)](https://www.django-rest-framework.org/)
[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![Coverage](https://img.shields.io/badge/coverage-85%25-success.svg)](https://pytest.org/)
---

## Table of Contents

1. [Project Overview](#-project-overview)
2. [Economic Foundation](#-economic-foundation)
3. [System Architecture](#-system-architecture)
4. [Technology Stack](#-technology-stack)
5. [Installation Guide](#-installation-guide)
6. [API Documentation](#-api-documentation)
7. [Database Schema](#-database-schema)
8. [Celery Tasks](#-celery-tasks)
9. [Testing Guide](#-testing-guide)
10. [Deployment](#-deployment)
11. [Environment Variables](#-environment-variables)
12. [Data Sources](#data-sources)
13. [Troubleshooting](#-troubleshooting)
14. [Academic References](#-academic-references)

---

## Project Overview

ElasticBot V2.0 is a production-ready Django REST API that calculates **price elasticity of demand** for the USDT/BOB cryptocurrency pair in the Bolivian market.

### Research Question

**Is USDT demand in Bolivia elastic, inelastic, or unitary elastic?**

### Hypothesis

> USDT exhibits **inelastic demand** (|Ed| < 1) in Bolivia's restricted currency market, as it serves as a necessity good for value preservation rather than speculation.

### Context: Bolivian Cryptocurrency Market

- **Official exchange rate:** 6.96 BOB/USD (fixed since 2011)
- **Currency restrictions:** BCB Resolution 144/2020 limits USD access
- **Informal economy:** ~60% of transactions
- **USDT role:** Dollar substitute for savings and international payments

### Key Features

- [x] **Anonymous API** - No authentication required  
- [x] **Dual Methods** - Midpoint elasticity + Log-log regression  
- [x] **Real-time Data** - Hourly Binance P2P collection via Celery  
- [x] **AI Interpretation** - AWS Bedrock (Llama 4 Maverick)  
- [x] **Scenario Simulator** - Test hypothetical scenarios  
- [x] **PDF Reports** - Professional export with charts  
- [x] **Rate Limiting** - IP-based protection  
- [x] **85%+ Test Coverage** - Comprehensive testing  
- [x] **Production Ready** - Railway/Render deployment

---

## Economic Foundation

### Price Elasticity of Demand

**Definition:** Responsiveness of quantity demanded to price changes.

**Midpoint (Arc) Formula:**
```
Ed = [(Q₂ - Q₁) / ((Q₂ + Q₁)/2)] / [(P₂ - P₁) / ((P₂ + P₁)/2)]
```

**Log-Log Regression:**
```
log(Q) = α + β·log(P) + ε
```
Where β is the elasticity coefficient.

### Classification

| Elasticity | Type | Meaning |
|------------|------|---------|
| \|Ed\| > 1 | **Elastic** | Quantity highly responsive to price |
| \|Ed\| < 1 | **Inelastic** | Quantity less responsive to price |
| \|Ed\| ≈ 1 | **Unitary** | Proportional response |

### Why USDT Should Be Inelastic in Bolivia

1. **No dollar alternatives** - BCB restrictions force USDT adoption
2. **Value preservation** - Protection against 5-15% inflation
3. **International payments** - Only practical option for businesses
4. **Informal economy** - Essential for cross-border transactions

---

## System Architecture

### High-Level Design

```
┌─────────────────┐
│  React Frontend │
└────────┬────────┘
         │ REST API
         ▼
┌─────────────────────────────┐
│   Django REST Framework     │
│  ┌──────┐  ┌──────────┐   │
│  │Market│  │Elasticity│   │
│  │ Data │──▶│Calculator│   │
│  └──────┘  └────┬─────┘   │
│       │         │          │
│       │    ┌────▼────┐    │
│       │    │   AI    │    │
│       │    │Interpret│    │
│       │    └─────────┘    │
└───────┼─────────┬──────────┘
        │         │
        ▼         ▼
┌──────────┐  ┌────────┐
│PostgreSQL│  │ Redis  │
└──────────┘  └───┬────┘
                  │
                  ▼
           ┌──────────────┐
           │Celery Workers│
           └──────┬───────┘
                  │
                  ▼
           ┌──────────────┐
           │External APIs │
           │• Binance P2P │
           │• AWS Bedrock │
           └──────────────┘
```

### Apps Structure

```
apps/
├── market_data/       # Data collection from Binance
├── elasticity/        # Calculation engine
├── ai_interpretation/ # AWS Bedrock integration
├── simulator/         # Scenario testing
└── reports/           # PDF generation
```

---

## Technology Stack

### Backend
- Django 5.2, Django REST Framework 3.16
- PostgreSQL 15, Redis 7
- Celery 5.3 + Beat scheduler

### Data Science
- NumPy 1.26, SciPy 1.11
- scikit-learn, statsmodels

### External APIs
- AWS Bedrock (Llama 4 Maverick)
- Binance P2P API

### Testing
- pytest 7.4, pytest-django, pytest-cov
- flake8, black

---

## Installation Guide

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+

### Setup Steps

#### 1. Clone Repository
```bash
git clone https://github.com/your-org/ficct-elasticbot-backend.git
cd ficct-elasticbot-backend
```

#### 2. Create Virtual Environment
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS
```

#### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### 4. Configure Environment
```bash
cp .env.example .env
# Edit .env with your values
```

**Required variables:**
```env
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgresql://user:password@localhost:5432/elasticbot
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
```

#### 5. Run Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

#### 6. Create Superuser (Optional)
```bash
python manage.py createsuperuser
```

#### 7. Start Services

**Terminal 1 - Django:**
```bash
python manage.py runserver
```

**Terminal 2 - Celery Worker:**
```bash
celery -A base worker -l info --pool=solo  # Windows
celery -A base worker -l info  # Linux/macOS
```

**Terminal 3 - Celery Beat:**
```bash
celery -A base beat -l info
```

#### 8. Verify Installation

Open: http://localhost:8000/api/v1/

---

## API Documentation

### Base URL

- **Development:** `http://localhost:8000/api/v1/`
- **Production:** `https://your-domain.com/api/v1/`

### Authentication

**None required.** All endpoints allow anonymous access.

### Rate Limiting (Per IP)

| Endpoint | Limit | Window |
|----------|-------|--------|
| General | 100 req | 1 hour |
| Calculations | 10 req | 1 hour |
| AI Interpretations | 5 req | 1 hour |

### Response Format

**Success:**
```json
{
  "field1": "value1",
  "field2": "value2"
}
```

**Error:**
```json
{
  "error": "Error type",
  "detail": "Message"
}
```

---

### Market Data Endpoints

#### `GET /api/v1/market-data/`
List market snapshots with pagination.

**Query Parameters:**
- `page` - Page number (default: 1)
- `page_size` - Per page (default: 50, max: 100)

**Response 200:**
```json
{
  "count": 1440,
  "next": "http://localhost:8000/api/v1/market-data/?page=2",
  "previous": null,
  "results": [
    {
      "id": 12345,
      "timestamp": "2025-11-18T20:00:00Z",
      "average_sell_price": 7.05,
      "average_buy_price": 6.98,
      "total_volume": 142500.50,
      "spread_percentage": 1.00,
      "num_active_traders": 23,
      "data_quality_score": 0.92,
      "is_high_quality": true
    }
  ]
}
```

#### `GET /api/v1/market-data/latest/`
Get most recent snapshot.

**Response 200:**
```json
{
  "id": 12345,
  "timestamp": "2025-11-18T20:00:00Z",
  "average_sell_price": 7.05,
  "average_buy_price": 6.98,
  "total_volume": 142500.50,
  "spread_percentage": 1.00,
  "num_active_traders": 23,
  "data_quality_score": 0.92
}
```

---

### Elasticity Calculation Endpoints

#### `POST /api/v1/elasticity/calculate/`
Create new calculation (async processing).

**Request:**
```json
{
  "method": "midpoint",
  "start_date": "2025-11-01T00:00:00Z",
  "end_date": "2025-11-18T23:59:59Z",
  "window_size": "daily"
}
```

**Parameters:**
- `method` - `"midpoint"` or `"regression"`
- `start_date` - ISO 8601 format
- `end_date` - Max 90 days from start
- `window_size` - `"hourly"`, `"daily"`, or `"weekly"`

**Response 202:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PENDING",
  "method": "MIDPOINT",
  "start_date": "2025-11-01T00:00:00Z",
  "end_date": "2025-11-18T23:59:59Z",
  "window_size": "DAILY",
  "created_at": "2025-11-18T20:15:30Z"
}
```

#### `GET /api/v1/elasticity/{id}/`
Get calculation results (poll after POST).

**Response 200 (Completed):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "COMPLETED",
  "method": "MIDPOINT",
  "elasticity_coefficient": -0.8734,
  "elasticity_magnitude": 0.8734,
  "classification": "INELASTIC",
  "confidence_interval_95": {
    "lower": -1.1203,
    "upper": -0.6265
  },
  "data_points_used": 18,
  "average_data_quality": 0.89,
  "is_significant": true,
  "completed_at": "2025-11-18T20:15:45Z"
}
```

**Response 200 (Processing):**
```json
{
  "id": "550e8400-...",
  "status": "PROCESSING",
  "elasticity_coefficient": null
}
```

#### `GET /api/v1/elasticity/recent/`
Get recent calculations for your IP.

**Response 200:**
```json
{
  "count": 3,
  "results": [
    {
      "id": "550e8400-...",
      "status": "COMPLETED",
      "method": "MIDPOINT",
      "elasticity_coefficient": -0.8734,
      "classification": "INELASTIC",
      "created_at": "2025-11-18T20:15:30Z"
    }
  ]
}
```

---

### AI Interpretation Endpoints

#### `POST /api/v1/interpret/generate/`
Generate AI interpretation (rate limit: 5/hour).

**Request:**
```json
{
  "calculation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response 200:**
```json
{
  "calculation_id": "550e8400-...",
  "interpretation": "**Análisis de Elasticidad: Demanda Inelástica**\n\nEl coeficiente calculado es -0.8734, indicando demanda inelástica...",
  "generated_at": "2025-11-18T20:30:00Z",
  "cached": false,
  "model": "meta.llama-4-maverick-v1:0"
}
```

**Response 429 (Rate Limit):**
```json
{
  "error": "Rate limit exceeded",
  "detail": "Maximum 5 requests per 3600s allowed",
  "retry_after": 3600
}
```

---

### Simulator Endpoints

#### `POST /api/v1/simulator/scenario/`
Simulate hypothetical scenario.

**Request:**
```json
{
  "price_initial": 7.00,
  "price_final": 7.20,
  "quantity_initial": 125000,
  "quantity_final": 118000
}
```

**Response 200:**
```json
{
  "elasticity": -0.9234,
  "abs_value": 0.9234,
  "classification": "inelastic",
  "pct_change_price": 2.82,
  "pct_change_quantity": -5.77
}
```

---

### Report Endpoints

#### `GET /api/v1/reports/{calculation_id}/pdf/`
Download PDF report for calculation.

**Response 200:**
```
Content-Type: application/pdf
Content-Disposition: attachment; filename="elasticity_550e8400.pdf"
```

---

## Database Schema

### Core Models

#### ElasticityCalculation
```python
id = UUID (primary key)
method = VARCHAR (MIDPOINT/REGRESSION)
start_date = DATETIME
end_date = DATETIME
window_size = VARCHAR (HOURLY/DAILY/WEEKLY)
status = VARCHAR (PENDING/PROCESSING/COMPLETED/FAILED)
elasticity_coefficient = DECIMAL(10,6)
classification = VARCHAR
confidence_interval_95 = JSON
data_points_used = INTEGER
average_data_quality = DECIMAL(5,4)
is_significant = BOOLEAN
error_message = TEXT
client_ip = INET
created_at = DATETIME
completed_at = DATETIME
```

#### MarketSnapshot
```python
id = BIGINT (primary key)
timestamp = DATETIME
average_sell_price = DECIMAL(10,2)
average_buy_price = DECIMAL(10,2)
total_volume = DECIMAL(15,2)
spread_percentage = DECIMAL(5,2)
num_active_traders = INTEGER
data_quality_score = DECIMAL(5,4)
raw_response = JSONB
created_at = DATETIME
```

#### Report
```python
id = UUID (primary key)
calculation_id = FK(ElasticityCalculation)
file_path = VARCHAR
s3_url = VARCHAR
generated_at = DATETIME
```

---

## Celery Tasks

### Scheduled Tasks (Celery Beat)

| Task | Schedule | Description |
|------|----------|-------------|
| `fetch_binance_data` | Every hour | Collect USDT/BOB market data from Binance P2P |
| `fetch_bcb_exchange_rate` | Daily 8 AM | Official BOB/USD rate from BCB |
| `cleanup_old_data` | Daily 3 AM | Remove snapshots older than 90 days |

### Async Tasks

| Task | Trigger | Description |
|------|---------|-------------|
| `process_elasticity_calculation` | API request | Async elasticity calculation with full validation |

### Configuration

**Celery settings in `base/settings.py`:**
```python
CELERY_BROKER_URL = env('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = env('REDIS_URL')
CELERY_TASK_ALWAYS_EAGER = False  # Async mode
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'America/La_Paz'
```

**Beat schedule in `base/celery.py`:**
```python
beat_schedule = {
    'fetch-binance-hourly': {
        'task': 'apps.market_data.tasks.fetch_binance_data',
        'schedule': crontab(minute=0),  # Every hour
    },
    'fetch-bcb-daily': {
        'task': 'apps.market_data.tasks.fetch_bcb_exchange_rate',
        'schedule': crontab(hour=8, minute=0),  # 8 AM daily
    },
    'cleanup-daily': {
        'task': 'apps.market_data.tasks.cleanup_old_data',
        'schedule': crontab(hour=3, minute=0),  # 3 AM daily
    },
}
```

---

## Testing Guide

### Running Tests

**All tests with coverage:**
```bash
pytest apps/ --cov=apps --cov-report=term-missing --cov-report=html
```

**Specific app:**
```bash
pytest apps/elasticity/ -v
```

**With coverage threshold:**
```bash
pytest apps/ --cov=apps --cov-fail-under=85
```

### Test Structure

```
apps/
├── elasticity/tests/
│   ├── test_midpoint.py (20+ tests)
│   ├── test_regression.py (15+ tests)
│   └── test_viewsets.py
├── market_data/tests/
│   ├── test_binance_service.py
│   └── test_validators.py
├── ai_interpretation/tests/
│   └── test_bedrock.py (mocked AWS)
└── simulator/tests/
    └── test_scenarios.py
```

### Coverage Requirements

- **Minimum:** 85% overall
- **Target:** 90%+
- **Critical paths:** 100% (calculators, validators)

### Example Test

```python
@pytest.mark.django_db
def test_midpoint_elasticity_inelastic():
    calculator = MidpointElasticityCalculator()
    result = calculator.calculate(
        price_data=[7.00, 7.10],
        quantity_data=[125000, 120000]
    )
    assert result['elasticity'] < -0.1
    assert result['classification'] == 'INELASTIC'
```

---

## Deployment

### Railway Deployment

**1. Install Railway CLI:**
```bash
npm install -g @railway/cli
railway login
```

**2. Initialize Project:**
```bash
railway init
railway link
```

**3. Add Environment Variables:**
```bash
railway variables set DATABASE_URL=<neon-postgresql-url>
railway variables set REDIS_URL=<redis-url>
railway variables set SECRET_KEY=<secret-key>
railway variables set AWS_ACCESS_KEY_ID=<key>
railway variables set AWS_SECRET_ACCESS_KEY=<secret>
```

**4. Deploy:**
```bash
railway up
```

### Render Deployment

**1. Create `render.yaml`:**
```yaml
services:
  - type: web
    name: elasticbot-api
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn base.wsgi:application
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
      - key: DATABASE_URL
        fromDatabase:
          name: elasticbot-db
          property: connectionString
```

**2. Push to GitHub and connect Render.**

### Production Checklist

- [ ] Set `DEBUG=False`
- [ ] Configure `ALLOWED_HOSTS`
- [ ] Use production database (Neon PostgreSQL)
- [ ] Configure Redis (Railway/Upstash)
- [ ] Set secure `SECRET_KEY`
- [ ] Configure AWS Bedrock credentials
- [ ] Enable HTTPS
- [ ] Set up monitoring (Sentry)
- [ ] Configure CORS properly
- [ ] Test all endpoints

---

## Environment Variables

### Required Variables

```env
# Django Core
SECRET_KEY=your-secret-key-min-50-chars
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database (Neon PostgreSQL recommended)
DATABASE_URL=postgresql://user:pass@host:5432/db?sslmode=require

# Redis (Railway/Upstash recommended)
REDIS_URL=redis://default:password@host:6379
CELERY_BROKER_URL=redis://default:password@host:6379

# AWS Bedrock (Optional - uses mock if not set)
AWS_ACCESS_KEY_ID=AKIAXXXXXXXXXXXXXXXX
AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
AWS_BEDROCK_REGION=us-east-1
AWS_BEDROCK_MODEL_ID=meta.llama-4-maverick-v1:0

# CORS (if frontend on different domain)
CORS_ALLOWED_ORIGINS=https://frontend.com,https://www.frontend.com

# Rate Limiting
RATELIMIT_ENABLE=True
```

### Optional Variables

```env
# JWT (if authentication needed in future)
JWT_SECRET_KEY=different-from-django-secret
JWT_ACCESS_TOKEN_LIFETIME=60
JWT_REFRESH_TOKEN_LIFETIME=1440

# Logging
LOG_LEVEL=INFO
SENTRY_DSN=https://xxx@sentry.io/xxx
```

---

## Data Sources

### Source Comparison

| Attribute | P2P Scraper | External OHLC API | P2P Historical JSON |
|-----------|-------------|-------------------|---------------------|
| **Quality Score** | 0.7+ | 0.95 | 0.80 |
| **Source ID** | `binance_p2p` | `external_ohlc_api` | `p2p_scrape_json` |
| **Volume Data** | ✅ Real volume | ❌ Not available (null) | ❌ Not available (0) |
| **Prices** | ✅ Real-time | ✅ Historical OHLC | ✅ Historical averages |
| **Used for Elasticity** | ❌ | ✅ | ❌ |
| **Used for Charts** | ✅ | ✅ (prices only) | ✅ |

### Primary: Binance P2P Scraper (Automated)

The system automatically collects USDT/BOB market data from Binance P2P every 30 minutes via Celery Beat.

**Data captured:**
- Average sell/buy prices
- **Total volume** (real trading volume from Binance P2P)
- Number of active traders
- Spread percentage

### Secondary: External OHLC API (Manual Import)

For historical data backfill when the database lacks sufficient data.

```
⚠️ CRITICAL: This API has USAGE-BASED PRICING!
Every request costs money. Use sparingly.
```

**Important:** The OHLC API does **NOT provide volume data**. It only returns price candles (open, high, low, close). The `total_volume` field is set to `null` for OHLC records. For volume analysis, use P2P scraper data.

### Tertiary: Historical P2P JSON Import

For importing legacy P2P scrape data from `p2p_scrapes.json`.

```bash
# Preview import
python manage.py import_p2p_scrapes --dry-run

# Execute import
python manage.py import_p2p_scrapes --confirm
```

**Note:** Historical P2P data has `total_volume=0` (volume was not captured by the original scraper). Use current P2P scraper data for volume analysis.

**Setup:**
1. Add to `.env`:
   ```
   EXTERNAL_OHLC_API_URL='https://your-api-endpoint.amazonaws.com/prod/ohlc'
   ```

**Usage:**
```bash
# Test configuration without making API call
python manage.py import_ohlc_history --dry-run

# Actually import data (requires --confirm flag)
python manage.py import_ohlc_history --confirm

# Skip existing data check
python manage.py import_ohlc_history --confirm --force
```

**Inside Docker:**
```bash
docker exec elasticbot-web python manage.py import_ohlc_history --confirm
```

**What it does:**
- Imports 200 hourly candles (~8 days of USDT/BOB data)
- Data is stored permanently for all future calculations
- Idempotent: safe to re-run, duplicates are skipped

**Cost-Saving Design:**
- `--confirm` flag required to prevent accidental execution
- Warns if data already exists before making API call
- Fixed parameters optimized for maximum value per call
- NO automated/scheduled execution - manual only

### Data Quality Policy

The elasticity calculation engine uses **exclusively** high-quality data from the external OHLC API:

| Field | Policy |
|-------|--------|
| `data_quality_score` | Must be >= 0.95 (external API marker) |
| `raw_response.source` | Must be `external_ohlc_api` |
| `num_active_traders` | **NOT USED** in any calculation (always 0) |

**Cleanup Command:**
```bash
# Preview what will be deleted
docker exec elasticbot-web python manage.py cleanup_market_data --dry-run

# Execute cleanup (removes non-external API data)
docker exec elasticbot-web python manage.py cleanup_market_data --confirm
```

**Design Principles:**
1. **Single Source of Truth:** Only external OHLC API data is used for calculations
2. **No Runtime Dependencies:** System operates on local database only
3. **Full OHLC Preserved:** `raw_response` contains complete candle data (open, high, low, close) for future frontend charting
4. **No Automatic API Calls:** External API was called once; future updates require manual intervention

### Extending Historical Data

**API Limitation:** The external API returns the *last N points* only - no offset or date range parameters. To extend history, run imports periodically (manually) over time.

**Timeframe Options:**
| Timeframe | 200 points = | Best for |
|-----------|--------------|----------|
| `10m` | ~33 hours | High-frequency analysis |
| `30m` | ~4 days | Intraday patterns |
| `1h` | ~8 days | Standard elasticity (recommended) |

**Building History Over Time:**
```bash
# Check current coverage
curl http://localhost:8000/api/v1/market-data/coverage/

# Run import to capture latest data (can be repeated weekly/monthly)
docker exec elasticbot-web python manage.py import_ohlc_history --confirm

# Example with different timeframe
docker exec elasticbot-web python manage.py import_ohlc_history --confirm --timeframe 30m
```

**Strategy for 30+ Days of History:**
1. Run initial import (~8 days)
2. Wait 1 week, run again (captures new week + overlap)
3. Repeat weekly to accumulate ~30 days after 4 weeks
4. Each run is idempotent - duplicates are skipped

**Cost Control:**
- Each execution = 1 paid API call
- The command shows current coverage and asks for confirmation
- Use `--dry-run` to preview without calling API
- Never automate this command

### Coverage Endpoint for Frontend

The frontend can query the data coverage range:

```bash
GET /api/v1/market-data/coverage/
```

**Response:**
```json
{
  "coverage_start": "2025-11-20T18:00:00+00:00",
  "coverage_end": "2025-11-29T01:00:00+00:00",
  "total_records": 200,
  "span_days": 8.29,
  "span_hours": 199,
  "data_source": "external_ohlc_api",
  "quality_threshold": 0.95,
  "timeframes": ["1h"]
}
```

Use this to:
- Set min/max bounds on date pickers
- Show data availability in the UI

### Aggregated Data Endpoint (Backend-Driven Charts)

The frontend should use this endpoint instead of doing client-side aggregation:

```bash
GET /api/v1/market-data/aggregated/?time_range=7d&granularity=daily&source=all
```

**Parameters:**
| Parameter | Options | Description |
|-----------|---------|-------------|
| `time_range` | `24h`, `7d`, `30d`, `90d` | Preset time range |
| `granularity` | `hourly`, `daily`, `weekly` | Aggregation level |
| `source` | `p2p`, `ohlc`, `all` | Data source filter |
| `start_date` | ISO 8601 | Custom start (use with end_date) |
| `end_date` | ISO 8601 | Custom end (use with start_date) |

**Response:**
```json
{
  "time_range": "7d",
  "granularity": "daily",
  "coverage_start": "2025-11-22T00:00:00+00:00",
  "coverage_end": "2025-11-28T00:00:00+00:00",
  "span_days": 6.0,
  "data_source": "p2p_scrape_json",
  "total_records": 168,
  "aggregated_points": 7,
  "points": [
    {
      "timestamp": "2025-11-22T00:00:00+00:00",
      "average_buy_price": 6.92,
      "average_sell_price": 7.05,
      "total_volume": null,
      "spread_percentage": 1.86,
      "record_count": 24,
      "has_volume_data": false
    }
  ]
}
```

**Notes:**
- `total_volume` is `null` when source is `ohlc` (OHLC API doesn't provide volume)
- `has_volume_data` indicates if volume data was available for the aggregation period
- For volume charts, use `source=p2p` to ensure real volume data

### Maintenance Commands

**Fix OHLC Volume (backfill):**
```bash
# Preview fix (shows synthetic volumes that will be set to null)
python manage.py fix_ohlc_volume --dry-run

# Execute fix
python manage.py fix_ohlc_volume --confirm
```

This command fixes OHLC records that have incorrect synthetic volume values (from a previous bug that calculated fake volume from price ranges). After running, OHLC records will have `total_volume=null` as they should.

---

## Troubleshooting

### Common Issues

#### 1. Migration Errors
```bash
# Reset migrations (development only!)
python manage.py migrate --fake-initial
```

#### 2. Celery Not Picking Up Tasks
```bash
# Restart worker with purge
celery -A base purge -f
celery -A base worker -l info --pool=solo
```

#### 3. Redis Connection Error
```bash
# Test Redis connection
redis-cli -u $REDIS_URL ping
# Should return: PONG
```

#### 4. AWS Bedrock Errors
- Verify AWS credentials are set
- Check IAM permissions for Bedrock
- Ensure region supports Llama 4 Maverick
- System falls back to mock if Bedrock unavailable

#### 5. Database Connection Errors
```bash
# Test DATABASE_URL format
python -c "import dj_database_url; print(dj_database_url.config())"
```

#### 6. Import Errors After New App
```bash
# Reinstall and restart
pip install -e .
python manage.py collectstatic --noinput
```

#### 7. Calculations Fail with "No market data available"
This means the database lacks MarketSnapshot records for the requested date range.

```bash
# Check available data range
docker exec elasticbot-web python manage.py shell -c "
from apps.market_data.models import MarketSnapshot
first = MarketSnapshot.objects.order_by('timestamp').first()
last = MarketSnapshot.objects.order_by('timestamp').last()
print(f'Data range: {first.timestamp if first else None} to {last.timestamp if last else None}')
print(f'Total records: {MarketSnapshot.objects.count()}')
"

# Import historical data if needed
docker exec elasticbot-web python manage.py import_ohlc_history --timeframe 1h --points 200
```

### Elasticity Calculation Execution Mode

The elasticity calculation endpoint supports two execution modes:

| Mode | Setting | Behavior |
|------|---------|----------|
| **Sync** (default) | `ELASTICITY_ASYNC_ENABLED=False` | Calculation runs in the request (5-15s latency) |
| **Async** | `ELASTICITY_ASYNC_ENABLED=True` | Calculation queued to Celery (requires Redis) |

**When to use Sync mode:**
- Redis is not available or unstable
- You want guaranteed calculation completion
- Development/testing without Redis infrastructure

**When to use Async mode:**
- Redis and Celery are running reliably
- You need non-blocking API responses
- High concurrency with multiple simultaneous calculations

**Configuration:**
```bash
# .env file
ELASTICITY_ASYNC_ENABLED=False  # Sync mode (default, no Redis needed)
# or
ELASTICITY_ASYNC_ENABLED=True   # Async mode (requires Redis)
```

**Trade-offs:**

| Aspect | Sync Mode | Async Mode |
|--------|-----------|------------|
| Request latency | 5-15 seconds | Instant (202 response) |
| Redis dependency | Not required | Required |
| Reliability | Always works | Fails if Redis is down |
| Response | Complete result | Requires polling |

**Automatic Fallback:**
When `ELASTICITY_ASYNC_ENABLED=True` but Redis is unavailable, the system automatically falls back to sync mode and logs a warning.

### Debug Mode

Enable detailed logging:
```python
# base/settings.py
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
}
```

---

## Academic References

### Economic Theory

1. **Mankiw, N. G.** (2020). *Principles of Microeconomics* (9th ed.). Cengage Learning.
   - Chapter 5: Elasticity and Its Application

2. **Varian, H. R.** (1992). *Microeconomic Analysis* (3rd ed.). W.W. Norton & Company.
   - Chapter 8: Demand Functions

3. **Pindyck, R. S., & Rubinfeld, D. L.** (2018). *Microeconomics* (9th ed.). Pearson.
   - Chapter 2: The Basics of Supply and Demand

### Econometric Methods

4. **Wooldridge, J. M.** (2020). *Introductory Econometrics: A Modern Approach* (7th ed.). Cengage Learning.

5. **Stock, J. H., & Watson, M. W.** (2020). *Introduction to Econometrics* (4th ed.). Pearson.

### Cryptocurrency Markets

6. **Baur, D. G., Hong, K., & Lee, A. D.** (2018). Bitcoin: Medium of exchange or speculative assets? *Journal of International Financial Markets, Institutions and Money*, 54, 177-189.

7. **Kristoufek, L.** (2013). Bitcoin meets Google Trends and Wikipedia: Quantifying the relationship between phenomena of the Internet era. *Scientific Reports*, 3(1), 1-7.

### Bolivian Economic Context

8. **Banco Central de Bolivia** (2023). *Boletín Informativo*.

9. **Instituto Nacional de Estadística - Bolivia** (2024). *Índice de Precios al Consumidor*.

### Technical Documentation

10. **Django Project** (2024). Django Documentation. https://docs.djangoproject.com/

11. **Django REST Framework** (2024). https://www.django-rest-framework.org/

12. **AWS** (2024). Amazon Bedrock Documentation. https://docs.aws.amazon.com/bedrock/
