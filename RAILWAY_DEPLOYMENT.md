# Railway Deployment Guide - ElasticBot Backend

## Architecture Overview

ElasticBot requires **THREE services** running simultaneously:

1. **Web** - Django REST API (Gunicorn)
2. **Worker** - Celery Worker (async task processing)
3. **Beat** - Celery Beat (scheduled task scheduler)

All three use the **same Docker image** but with different `SERVICE_TYPE` configurations.

---

## Prerequisites

1. Railway account with a project
2. Redis addon (or external Redis like Upstash)
3. PostgreSQL database (Railway Postgres or external)
4. Environment variables configured

---

## Step-by-Step Setup

### Step 1: Create the Web Service (Main Backend)

This may already exist as `ficct-elasticbot-backend`.

1. Go to Railway Dashboard → Your Project
2. If not exists, click **"New Service"** → **"GitHub Repo"**
3. Select `ficct-elasticbot-backend` repository
4. Railway will auto-detect the Dockerfile

**Environment Variables for Web:**
```env
SERVICE_TYPE=web
PORT=8000
DEBUG=False
SECRET_KEY=your-secret-key
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
CELERY_BROKER_URL=${{Redis.REDIS_URL}}
CELERY_RESULT_BACKEND=${{Redis.REDIS_URL}}
ALLOWED_HOSTS=your-domain.railway.app,localhost
```

### Step 2: Create the Celery Worker Service

1. In Railway Dashboard → Click **"New Service"**
2. Select **"GitHub Repo"** → Same repository
3. Name it: `celery-worker`

**Environment Variables for Worker:**
```env
SERVICE_TYPE=worker
CELERY_LOG_LEVEL=info
CELERY_CONCURRENCY=2
DEBUG=False
SECRET_KEY=your-secret-key
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
CELERY_BROKER_URL=${{Redis.REDIS_URL}}
CELERY_RESULT_BACKEND=${{Redis.REDIS_URL}}
```

**Important:** Copy ALL environment variables from the Web service, then:
- Change `SERVICE_TYPE=worker`
- Remove `PORT` (worker doesn't need it)

### Step 3: Create the Celery Beat Service

1. In Railway Dashboard → Click **"New Service"**
2. Select **"GitHub Repo"** → Same repository
3. Name it: `celery-beat`

**Environment Variables for Beat:**
```env
SERVICE_TYPE=beat
CELERY_LOG_LEVEL=info
DEBUG=False
SECRET_KEY=your-secret-key
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
CELERY_BROKER_URL=${{Redis.REDIS_URL}}
CELERY_RESULT_BACKEND=${{Redis.REDIS_URL}}
```

**Important:** Copy ALL environment variables from the Web service, then:
- Change `SERVICE_TYPE=beat`
- Remove `PORT` (beat doesn't need it)

---

## Using Shared Variables (Recommended)

To avoid duplicating variables across services:

1. Go to Project Settings → **Shared Variables**
2. Add common variables:
   ```
   SECRET_KEY=your-secret-key
   DEBUG=False
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   REDIS_URL=${{Redis.REDIS_URL}}
   CELERY_BROKER_URL=${{Redis.REDIS_URL}}
   CELERY_RESULT_BACKEND=${{Redis.REDIS_URL}}
   ```
3. Each service inherits shared variables automatically
4. Override `SERVICE_TYPE` per service

---

## Complete Environment Variables Reference

### Required for ALL Services

| Variable | Description | Example |
|----------|-------------|---------|
| `SERVICE_TYPE` | Service type | `web`, `worker`, or `beat` |
| `SECRET_KEY` | Django secret key | `your-super-secret-key` |
| `DATABASE_URL` | PostgreSQL connection | `${{Postgres.DATABASE_URL}}` |
| `REDIS_URL` | Redis connection | `${{Redis.REDIS_URL}}` |
| `CELERY_BROKER_URL` | Celery broker | `${{Redis.REDIS_URL}}` |
| `CELERY_RESULT_BACKEND` | Celery results | `${{Redis.REDIS_URL}}` |

### Web Service Only

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | HTTP port | `8000` |
| `ALLOWED_HOSTS` | Django allowed hosts | `localhost` |
| `GUNICORN_WORKERS` | Number of workers | `4` |
| `GUNICORN_TIMEOUT` | Request timeout | `120` |

### Worker Service Only

| Variable | Description | Default |
|----------|-------------|---------|
| `CELERY_CONCURRENCY` | Concurrent workers | `2` |
| `CELERY_LOG_LEVEL` | Log level | `info` |

### Beat Service Only

| Variable | Description | Default |
|----------|-------------|---------|
| `CELERY_LOG_LEVEL` | Log level | `info` |

### Optional (API Keys)

| Variable | Description |
|----------|-------------|
| `AWS_ACCESS_KEY_ID` | AWS for Bedrock AI |
| `AWS_SECRET_ACCESS_KEY` | AWS for Bedrock AI |
| `AWS_DEFAULT_REGION` | AWS region |

---

## Verification

### 1. Check Web Service Logs

Should show:
```
Starting Gunicorn web server...
[INFO] Starting gunicorn 21.x.x
[INFO] Listening at: http://0.0.0.0:8000
[INFO] Using worker: sync
```

### 2. Check Worker Service Logs

Should show:
```
Starting Celery worker...
[INFO] celery@hostname ready.
[INFO] Connected to redis://...
```

### 3. Check Beat Service Logs

Should show:
```
Starting Celery beat scheduler...
[INFO] DatabaseScheduler: Schedule changed.
[INFO] beat: Starting...
```

### 4. Verify Scheduled Tasks

Wait 30 minutes and check:
```sql
SELECT timestamp, average_sell_price 
FROM market_data_marketsnapshot 
ORDER BY timestamp DESC 
LIMIT 5;
```

You should see new snapshots every ~30 minutes.

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
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │     Web      │  │    Worker    │  │     Beat     │       │
│  │  (Gunicorn)  │  │   (Celery)   │  │   (Celery)   │       │
│  │              │  │              │  │              │       │
│  │ SERVICE_TYPE │  │ SERVICE_TYPE │  │ SERVICE_TYPE │       │
│  │    = web     │  │   = worker   │  │    = beat    │       │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘       │
│         │                 │                 │                │
│         └────────┬────────┴────────┬────────┘                │
│                  │                 │                         │
│         ┌────────▼─────────────────▼────────┐               │
│         │              Redis                 │               │
│         │     (Broker + Result Backend)      │               │
│         └───────────────────────────────────┘               │
│                          │                                   │
│         ┌────────────────▼──────────────────┐               │
│         │           PostgreSQL               │               │
│         │          (Database)                │               │
│         └───────────────────────────────────┘               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Success Criteria

✅ Three Railway services running:
- `ficct-elasticbot-backend` (web)
- `celery-worker`
- `celery-beat`

✅ Logs show:
- Web: Gunicorn listening
- Worker: Ready and connected to Redis
- Beat: Scheduler started

✅ Database receiving new MarketSnapshots every ~30 minutes

✅ At least FOUR consecutive snapshots with ~30 minute spacing
