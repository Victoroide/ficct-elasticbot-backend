# Railway Deployment Guide - ElasticBot Backend

## Architecture Overview

ElasticBot runs **THREE processes in a SINGLE container** using supervisord:

1. **Web** - Django REST API (Gunicorn) on port 8000
2. **Worker** - Celery Worker (async task processing)
3. **Beat** - Celery Beat (scheduled task scheduler)

This simplifies deployment to **ONE Railway service** instead of three.

---

## Prerequisites

1. Railway account with a project
2. Redis addon (or external Redis like Upstash)
3. PostgreSQL database (Railway Postgres or external)
4. Environment variables configured

---

## Step-by-Step Setup

### Step 1: Configure the Backend Service

Your service `ficct-elasticbot-backend` already exists. Just update the environment variables:

1. Go to Railway Dashboard → `ficct-elasticbot-backend` → **Variables**
2. Add/update these variables:

```env
# Required
PORT=8000
DEBUG=False
SECRET_KEY=your-secret-key
DATABASE_URL=${{Postgres.DATABASE_URL}}
ALLOWED_HOSTS=your-domain.railway.app,localhost

# Redis & Celery
REDIS_URL=${{Redis.REDIS_URL}}
CELERY_BROKER_URL=${{Redis.REDIS_URL}}
CELERY_RESULT_BACKEND=${{Redis.REDIS_URL}}

# Supervisord process configuration
GUNICORN_WORKERS=4
GUNICORN_TIMEOUT=120
CELERY_CONCURRENCY=2
CELERY_LOG_LEVEL=info
```

3. **Redeploy** the service

That's it! The single container runs all three processes via supervisord.

---

## Complete Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | HTTP port for Gunicorn | `8000` |
| `SECRET_KEY` | Django secret key | Required |
| `DATABASE_URL` | PostgreSQL connection | Required |
| `REDIS_URL` | Redis connection | Required |
| `CELERY_BROKER_URL` | Celery broker URL | Required |
| `CELERY_RESULT_BACKEND` | Celery results backend | Required |
| `ALLOWED_HOSTS` | Django allowed hosts | `localhost` |
| `GUNICORN_WORKERS` | Number of Gunicorn workers | `4` |
| `GUNICORN_TIMEOUT` | Request timeout seconds | `120` |
| `CELERY_CONCURRENCY` | Celery worker concurrency | `2` |
| `CELERY_LOG_LEVEL` | Celery log level | `info` |
| `DEBUG` | Django debug mode | `False` |

### Optional (API Keys)

| Variable | Description |
|----------|-------------|
| `AWS_ACCESS_KEY_ID` | AWS for Bedrock AI |
| `AWS_SECRET_ACCESS_KEY` | AWS for Bedrock AI |
| `AWS_DEFAULT_REGION` | AWS region |

---

## Verification

### 1. Check Startup Logs

When the container starts, you should see:

```
============================================================
🚀 ElasticBot Backend - Multi-Process Startup
============================================================
Time: Sat Nov 30 18:00:00 UTC 2025
============================================================

📡 Checking database connection...
✅ Database connection OK

📦 Running database migrations...
✅ Migrations complete

📁 Collecting static files...
✅ Static files collected

============================================================
📋 Configuration:
   PORT: 8000
   GUNICORN_WORKERS: 4
   CELERY_CONCURRENCY: 2
   CELERY_LOG_LEVEL: info
============================================================

🎬 Starting supervisord with 3 processes:
   1. 🌐 Web (Gunicorn) - HTTP API server
   2. ⚙️  Worker (Celery) - Async task processor
   3. ⏰ Beat (Celery Beat) - Scheduled task sender

📅 Scheduled Tasks:
   - P2P Scrape: Every 30 min (XX:00, XX:30)
   - BCB Rate: Daily at 8:00 AM Bolivia
   - Cleanup: Weekly on Sundays
============================================================
```

### 2. Check Process Logs

After supervisord starts, you'll see:

```
======================================================
🌐 [WEB] STARTING GUNICORN SERVER...
======================================================
[INFO] Starting gunicorn 21.x.x
[INFO] Listening at: http://0.0.0.0:8000

======================================================
⚙️  [WORKER] STARTING CELERY WORKER...
======================================================
[INFO] celery@hostname ready.

======================================================
⏰ [BEAT] STARTING CELERY BEAT SCHEDULER...
======================================================
[INFO] beat: Starting...
```

### 3. Verify Scheduled Tasks

Wait for the next :00 or :30 minute mark and check:
```sql
SELECT timestamp, average_sell_price 
FROM market_data_marketsnapshot 
ORDER BY timestamp DESC 
LIMIT 5;
```

Expected pattern (every 30 minutes):
```
2025-11-30 14:00:00  →  10.12
2025-11-30 14:30:00  →  10.11
2025-11-30 15:00:00  →  10.13
2025-11-30 15:30:00  →  10.12
```

---

## Scheduled Tasks

The following tasks run automatically:

| Task | Schedule | Description |
|------|----------|-------------|
| `fetch-binance-p2p-frequent` | Every 30 min | P2P market data scraping |
| `fetch-bcb-exchange-rate-daily` | Daily 8 AM (Bolivia) | BCB official rate |
| `cleanup-old-snapshots` | Weekly Sunday 3 AM | Data cleanup |

---

## Troubleshooting

### Worker not connecting to Redis

Check `CELERY_BROKER_URL` is correct:
```bash
# In Railway, use the reference syntax:
CELERY_BROKER_URL=${{Redis.REDIS_URL}}
```

### Beat not scheduling tasks

1. Verify `django_celery_beat` tables exist:
   ```bash
   python manage.py migrate django_celery_beat
   ```
2. Check beat logs for "Schedule changed" message

### No snapshots being created

1. Check Worker logs for task execution
2. Verify Beat is sending tasks
3. Check for errors in `fetch_binance_data` task

---

## Quick Reference Commands

### Local Testing with Docker Compose
```bash
# Start all services locally
docker-compose up -d

# View logs
docker-compose logs -f web
docker-compose logs -f worker
docker-compose logs -f beat

# Stop all
docker-compose down
```

### Manual Task Execution (Debugging)
```bash
# SSH into Railway or run locally
python manage.py run_scraper
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      Railway Project                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              ficct-elasticbot-backend                   │ │
│  │                  (Single Container)                     │ │
│  │                                                         │ │
│  │  ┌─────────────────────────────────────────────────┐   │ │
│  │  │              SUPERVISORD                         │   │ │
│  │  │                                                  │   │ │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐      │   │ │
│  │  │  │   Web    │  │  Worker  │  │   Beat   │      │   │ │
│  │  │  │ Gunicorn │  │  Celery  │  │  Celery  │      │   │ │
│  │  │  │  :8000   │  │  async   │  │scheduler │      │   │ │
│  │  │  └──────────┘  └──────────┘  └──────────┘      │   │ │
│  │  └─────────────────────────────────────────────────┘   │ │
│  └────────────────────────────────────────────────────────┘ │
│                            │                                 │
│         ┌──────────────────┴──────────────────┐             │
│         │              Redis                   │             │
│         │     (Broker + Result Backend)        │             │
│         └──────────────────┬──────────────────┘             │
│                            │                                 │
│         ┌──────────────────▼──────────────────┐             │
│         │           PostgreSQL                 │             │
│         │          (Database)                  │             │
│         └─────────────────────────────────────┘             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Success Criteria

✅ **ONE Railway service** running with supervisord managing 3 processes

✅ Logs show:
- `🚀 ElasticBot Backend - Multi-Process Startup`
- `🌐 [WEB] STARTING GUNICORN SERVER...`
- `⚙️  [WORKER] STARTING CELERY WORKER...`
- `⏰ [BEAT] STARTING CELERY BEAT SCHEDULER...`

✅ Database receiving new MarketSnapshots every **30 minutes exactly**:
```
14:00 → 14:30 → 15:00 → 15:30 → 16:00 ...
```

✅ At least **FOUR consecutive snapshots** with ~30 minute spacing
