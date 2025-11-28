# ElasticBot Backend API - Integration Guide

**Version:** 2.0.0  
**Last Updated:** November 2025  
**Audience:** Frontend Developers

---

## Table of Contents

1. [Overview](#overview)
2. [Base URLs](#base-urls)
3. [Authentication](#authentication)
4. [Rate Limiting](#rate-limiting)
5. [Response Format](#response-format)
6. [Error Handling](#error-handling)
7. [Endpoints](#endpoints)
   - [Market Data](#market-data-endpoints)
   - [Macroeconomic Indicators (BCB)](#macroeconomic-indicators-endpoints)
   - [Elasticity Analysis](#elasticity-analysis-endpoints)
   - [AI Interpretation](#ai-interpretation-endpoints)
   - [Scenario Simulator](#scenario-simulator-endpoints)
   - [Report Generation](#report-generation-endpoints)

---

## Overview

REST API to calculate **price elasticity of demand** for the USDT/BOB pair in the Bolivian P2P market.

**Features:**
- Anonymous API (no authentication required)
- JSON responses
- IP-based rate limiting
- Async processing for calculations
- Caching for performance

**Swagger Documentation:**
- Development: `http://localhost:8000/api/docs/`
- ReDoc: `http://localhost:8000/api/redoc/`

---

## Base URLs

| Environment | Base URL |
|-------------|----------|
| Development | `http://localhost:8000/api/v1/` |
| Production | `https://your-domain.com/api/v1/` |

---

## Authentication

**No authentication required.**

Anonymous API for academic purposes. All endpoints are publicly accessible.

---

## Rate Limiting

Limits by IP address:

| Category | Limit | Window |
|----------|-------|--------|
| Market Data | 100 requests | 1 hour |
| Elasticity Calculations | 10 requests | 1 hour |
| AI Interpretations | 5 requests | 1 hour |
| Simulator | 50 requests | 1 hour |
| Reports | 10 requests | 1 hour |

**HTTP 429 Response:**
```json
{
  "error": "Rate limit exceeded",
  "detail": "Maximum 10 requests per 3600s allowed",
  "retry_after": 3600
}
```

**Response Headers:**
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Remaining requests in window
- `Retry-After`: Seconds until reset (only on 429)

---

## Response Format

**Success Response:**
```json
{
  "field1": "value1",
  "field2": "value2"
}
```

**Paginated Response:**
```json
{
  "count": 1440,
  "next": "http://localhost:8000/api/v1/market-data/?page=2",
  "previous": null,
  "results": [...]
}
```

**Error Response:**
```json
{
  "error": "Error type",
  "detail": "Detailed message"
}
```

---

## Error Handling

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Process response |
| 201 | Created | Resource created successfully |
| 202 | Accepted | Async task started, poll for result |
| 400 | Bad Request | Check request body for validation errors |
| 404 | Not Found | Resource doesn't exist |
| 429 | Rate Limit | Wait `Retry-After` seconds |
| 500 | Server Error | Report issue, retry later |

---

## Endpoints

### Market Data Endpoints

#### GET /api/v1/market-data/

**Description:** List market snapshots with pagination.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| page | integer | 1 | Page number |
| page_size | integer | 50 | Items per page (max: 100) |

**Response 200:**
```json
{
  "count": 1440,
  "next": "http://localhost:8000/api/v1/market-data/?page=2",
  "previous": null,
  "results": [
    {
      "id": 12345,
      "timestamp": "2025-11-27T20:00:00Z",
      "average_sell_price": "7.05",
      "average_buy_price": "6.98",
      "total_volume": "142500.50",
      "spread_percentage": "1.00",
      "num_active_traders": 23,
      "data_quality_score": "0.92"
    }
  ]
}
```

**Cache:** 15 minutes

---

#### GET /api/v1/market-data/latest/

**Description:** Get the most recent market snapshot.

**Response 200:**
```json
{
  "id": 12345,
  "timestamp": "2025-11-27T20:00:00Z",
  "average_sell_price": "7.05",
  "average_buy_price": "6.98",
  "total_volume": "142500.50",
  "spread_percentage": "1.00",
  "num_active_traders": 23,
  "data_quality_score": "0.92"
}
```

**Response 404:**
```json
{
  "error": "No market data available",
  "detail": "Please wait for data collection to complete"
}
```

**Cache:** 5 minutes

---

#### GET /api/v1/market-data/{id}/

**Description:** Get a specific market snapshot by ID.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| id | integer | Snapshot ID |

**Response 200:** Same as `/latest/`

**Response 404:**
```json
{
  "detail": "Not found."
}
```

---

### Macroeconomic Indicators Endpoints

#### GET /api/v1/market-data/indicators/

**Description:** List macroeconomic indicators (BCB exchange rate, inflation).

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| page | integer | 1 | Page number |
| start_date | date | - | Filter from date (YYYY-MM-DD) |
| end_date | date | - | Filter to date (YYYY-MM-DD) |

**Response 200:**
```json
{
  "count": 30,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "date": "2025-11-27",
      "official_exchange_rate": "6.96",
      "monthly_inflation_rate": null,
      "accumulated_inflation": null,
      "source": "BCB",
      "created_at": "2025-11-27T12:00:00Z"
    }
  ]
}
```

---

#### GET /api/v1/market-data/indicators/latest/

**Description:** Get the most recent indicator (official BCB exchange rate).

**Response 200:**
```json
{
  "id": 1,
  "date": "2025-11-27",
  "official_exchange_rate": "6.96",
  "monthly_inflation_rate": null,
  "accumulated_inflation": null,
  "source": "BCB",
  "raw_data": {
    "venta": "6.96",
    "compra": "6.86",
    "url": "https://www.bcb.gob.bo/librerias/indicadores/otras/ultimo.php",
    "scraped_at": "2025-11-27T12:00:00Z"
  },
  "created_at": "2025-11-27T12:00:00Z"
}
```

**Response 404:**
```json
{
  "error": "No indicators available",
  "detail": "BCB data not yet collected"
}
```

**Notes:**
- Official BOB/USD exchange rate is fixed at ~6.96 since 2011
- Updated daily at 8:00 AM (Bolivia time)
- Source: Central Bank of Bolivia (BCB)
- `raw_data.venta`: Sell exchange rate (official)
- `raw_data.compra`: Buy exchange rate

---

### Elasticity Analysis Endpoints

#### POST /api/v1/elasticity/calculate/

**Description:** Create a new elasticity calculation (async processing).

**Rate Limit:** 10 requests/hour

**Request Body:**
```json
{
  "method": "midpoint",
  "start_date": "2025-11-01T00:00:00Z",
  "end_date": "2025-11-27T23:59:59Z",
  "window_size": "daily"
}
```

**Fields:**
| Field | Type | Required | Values | Description |
|-------|------|----------|--------|-------------|
| method | string | Yes | `midpoint`, `regression` | Calculation method |
| start_date | datetime | Yes | ISO 8601 | Analysis period start |
| end_date | datetime | Yes | ISO 8601 | Analysis period end |
| window_size | string | Yes | `hourly`, `daily`, `weekly` | Data aggregation window |

**Response 202 (Accepted):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PENDING",
  "method": "MIDPOINT",
  "start_date": "2025-11-01T00:00:00Z",
  "end_date": "2025-11-27T23:59:59Z",
  "window_size": "DAILY",
  "elasticity_coefficient": null,
  "classification": null,
  "created_at": "2025-11-27T20:15:30Z",
  "completed_at": null
}
```

**Important:** Async operation. Poll `GET /elasticity/{id}/` for results.

---

#### GET /api/v1/elasticity/{id}/

**Description:** Get calculation result by ID.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| id | UUID | Calculation ID |

**Response 200 (Completed):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "COMPLETED",
  "method": "MIDPOINT",
  "start_date": "2025-11-01T00:00:00Z",
  "end_date": "2025-11-27T23:59:59Z",
  "window_size": "DAILY",
  "elasticity_coefficient": "-0.8734",
  "elasticity_magnitude": 0.8734,
  "classification": "INELASTIC",
  "confidence_interval_95": {
    "lower": -1.12,
    "upper": -0.62
  },
  "r_squared": "0.84",
  "standard_error": "0.12",
  "data_points_used": 27,
  "average_data_quality": "0.89",
  "is_significant": true,
  "error_message": null,
  "created_at": "2025-11-27T20:15:30Z",
  "completed_at": "2025-11-27T20:15:45Z",
  "calculation_metadata": {
    "source": "Binance P2P",
    "currency_pair": "USDT/BOB"
  }
}
```

**Response 200 (Processing):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PROCESSING",
  "elasticity_coefficient": null,
  "classification": null
}
```

---

#### GET /api/v1/elasticity/{id}/status/

**Description:** Lightweight endpoint for polling calculation status.

**Response 200:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PROCESSING",
  "is_complete": false,
  "has_error": false,
  "created_at": "2025-11-27T20:15:30Z",
  "completed_at": null
}
```

---

#### GET /api/v1/elasticity/recent/

**Description:** Get recent calculations for your IP (last 24 hours).

**Response 200:**
```json
{
  "count": 3,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "COMPLETED",
      "method": "MIDPOINT",
      "elasticity_coefficient": "-0.8734",
      "classification": "INELASTIC",
      "created_at": "2025-11-27T20:15:30Z"
    }
  ]
}
```

---

### AI Interpretation Endpoints

#### POST /api/v1/interpret/generate/

**Description:** Generate AI-powered economic interpretation (AWS Bedrock).

**Rate Limit:** 5 requests/hour (due to AWS costs)

**Request Body:**
```json
{
  "calculation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response 200:**
```json
{
  "calculation_id": "550e8400-e29b-41d4-a716-446655440000",
  "interpretation": "El coeficiente de elasticidad calculado es -0.87, lo cual indica una demanda inelastica para el USDT en el mercado boliviano. Esto significa que los compradores de USDT son relativamente insensibles a cambios en el precio...",
  "generated_at": "2025-11-27T20:30:00Z",
  "cached": false,
  "model": "meta.llama-4-maverick-v1:0"
}
```

**Response 400 (Calculation not complete):**
```json
{
  "error": "Calculation not complete",
  "detail": "Current status: PROCESSING"
}
```

**Response 404:**
```json
{
  "error": "Calculation not found"
}
```

---

### Scenario Simulator Endpoints

#### POST /api/v1/simulator/scenario/

**Description:** Simulate a hypothetical elasticity scenario.

**Request Body:**
```json
{
  "price_initial": "7.00",
  "price_final": "7.20",
  "quantity_initial": "125000",
  "quantity_final": "118000"
}
```

**Fields:**
| Field | Type | Description |
|-------|------|-------------|
| price_initial | decimal | Initial USDT price in BOB |
| price_final | decimal | Final USDT price in BOB |
| quantity_initial | decimal | Initial quantity demanded |
| quantity_final | decimal | Final quantity demanded |

**Response 200:**
```json
{
  "elasticity": -0.9234,
  "abs_value": 0.9234,
  "classification": "inelastic",
  "percentage_change_quantity": -5.77,
  "percentage_change_price": 2.82,
  "quantity_change": -7000,
  "price_change": 0.20
}
```

---

### Report Generation Endpoints

#### GET /api/v1/reports/{calculation_id}/pdf/

**Description:** Download PDF report for a calculation.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| calculation_id | UUID | Calculation ID |

**Response 200:**
```
Content-Type: application/pdf
Content-Disposition: attachment; filename="elasticity_550e8400.pdf"
```

**Response 400:**
```json
{
  "error": "Calculation not complete"
}
```

**Response 404:**
```json
{
  "error": "Calculation not found"
}
```

---

## Async Polling Pattern

For elasticity calculations, follow this flow:

1. **POST** `/api/v1/elasticity/calculate/` → Receive `id` and `status: "PENDING"`
2. **Poll** every 2 seconds to `/api/v1/elasticity/{id}/status/`
3. When `is_complete: true` → **GET** `/api/v1/elasticity/{id}/` for full result
4. If `has_error: true` → Display `error_message`
5. **Recommended timeout:** 60 seconds (30 attempts × 2 seconds)

---

## Important Notes

1. **Decimal Precision:** All monetary values are returned as strings to preserve precision.

2. **Timestamps:** ISO 8601 format with UTC timezone.

3. **Caching:** Market data endpoints are cached. Respect the indicated cache times.

4. **CORS:** Development allows `localhost:5173`. Contact backend team for production origins.

5. **WebSocket:** Not currently supported. Use polling for real-time updates.

6. **BCB Exchange Rate:** Updated daily at 8:00 AM Bolivia (12:00 UTC). Official rate is ~6.96 BOB/USD since 2011.

---

**Questions?** Check Swagger documentation at `/api/docs/`.
