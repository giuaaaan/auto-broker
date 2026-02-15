# API Documentation - Auto-Broker Platform

## BIG TECH 100 Standards - REST API Reference

---

## Base URL

```
Production:  https://api.auto-broker.com/v1
Staging:     https://api-staging.auto-broker.com/v1
Local:       http://localhost:8000/v1
```

---

## Authentication

All API requests require authentication using JWT Bearer tokens.

```bash
# Request Header
Authorization: Bearer <your-jwt-token>
```

### Obtaining a Token

```bash
curl -X POST https://api.auto-broker.com/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "your-password"
  }'
```

**Response:**
```json
{
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "Bearer",
    "expires_in": 3600
  },
  "meta": {
    "request_id": "req_123456",
    "timestamp": "2024-01-15T12:00:00Z"
  }
}
```

---

## Response Format

### Success Response

```json
{
  "data": { ... },
  "meta": {
    "request_id": "uuid-v4",
    "timestamp": "2024-01-15T12:00:00Z",
    "version": "1.0.0"
  },
  "error": null
}
```

### Error Response

```json
{
  "data": null,
  "meta": {
    "request_id": "uuid-v4",
    "timestamp": "2024-01-15T12:00:00Z"
  },
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input parameters",
    "details": [
      {
        "field": "price",
        "message": "Must be a positive number"
      }
    ]
  }
}
```

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | OK - Successful GET, PUT, DELETE |
| 201 | Created - Successful POST |
| 204 | No Content - Successful DELETE (no body) |
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Authentication required |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource doesn't exist |
| 409 | Conflict - Resource conflict |
| 422 | Unprocessable Entity - Validation error |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error |
| 503 | Service Unavailable |

---

## Vehicles API

### List Vehicles

```bash
GET /v1/vehicles
```

**Query Parameters:**

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `page` | integer | Page number | 1 |
| `per_page` | integer | Items per page (max 100) | 20 |
| `make` | string | Filter by manufacturer | - |
| `model` | string | Filter by model | - |
| `year_min` | integer | Minimum year | - |
| `year_max` | integer | Maximum year | - |
| `price_min` | number | Minimum price | - |
| `price_max` | number | Maximum price | - |
| `fuel_type` | string | Filter by fuel type | - |
| `sort` | string | Sort field (created_at, price, year) | created_at |
| `order` | string | Sort order (asc, desc) | desc |

**Example Request:**
```bash
curl -X GET "https://api.auto-broker.com/v1/vehicles?make=BMW&price_max=50000&page=1" \
  -H "Authorization: Bearer <token>"
```

**Example Response:**
```json
{
  "data": {
    "items": [
      {
        "id": "veh_123456789",
        "make": "BMW",
        "model": "X5",
        "year": 2023,
        "mileage": 15000,
        "fuel_type": "diesel",
        "transmission": "automatic",
        "price": 45000.00,
        "currency": "EUR",
        "color": "black",
        "vin": "WBA12345678901234",
        "status": "available",
        "images": [
          "https://cdn.auto-broker.com/vehicles/veh_123456789/img1.jpg"
        ],
        "created_at": "2024-01-10T08:30:00Z",
        "updated_at": "2024-01-14T16:45:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 156,
      "total_pages": 8
    }
  },
  "meta": {
    "request_id": "req_abc123",
    "timestamp": "2024-01-15T12:00:00Z"
  }
}
```

### Get Vehicle by ID

```bash
GET /v1/vehicles/{id}
```

**Example:**
```bash
curl -X GET "https://api.auto-broker.com/v1/vehicles/veh_123456789" \
  -H "Authorization: Bearer <token>"
```

### Create Vehicle

```bash
POST /v1/vehicles
```

**Request Body:**
```json
{
  "make": "BMW",
  "model": "X5",
  "year": 2023,
  "mileage": 15000,
  "fuel_type": "diesel",
  "transmission": "automatic",
  "price": 45000.00,
  "currency": "EUR",
  "color": "black",
  "vin": "WBA12345678901234",
  "description": "Excellent condition, single owner"
}
```

**Validation Rules:**
- `make`: Required, 2-50 characters
- `model`: Required, 1-100 characters
- `year`: Required, 1900-current year
- `mileage`: Required, 0-10000000
- `price`: Required, > 0
- `vin`: Required, valid VIN format

### Update Vehicle

```bash
PUT /v1/vehicles/{id}
```

**Request Body:**
```json
{
  "price": 43000.00,
  "mileage": 16000,
  "description": "Updated description"
}
```

### Delete Vehicle

```bash
DELETE /v1/vehicles/{id}
```

---

## Pricing API

### Calculate Vehicle Price

```bash
POST /v1/pricing/calculate
```

**Request Body:**
```json
{
  "vehicle_id": "veh_123456789",
  "context": {
    "market": "IT",
    "condition": "excellent",
    "location": "Milan"
  },
  "adjustments": [
    {
      "type": "optional_equipment",
      "items": ["sunroof", "leather_seats"]
    }
  ]
}
```

**Response:**
```json
{
  "data": {
    "base_price": 45000.00,
    "adjustments": [
      {
        "type": "market_condition",
        "description": "High demand in region",
        "amount": 1200.00
      },
      {
        "type": "optional_equipment",
        "description": "Premium features",
        "amount": 2500.00
      }
    ],
    "final_price": 48700.00,
    "currency": "EUR",
    "confidence_score": 0.89,
    "valid_until": "2024-01-16T12:00:00Z"
  },
  "meta": {
    "request_id": "req_pricing_001",
    "timestamp": "2024-01-15T12:00:00Z"
  }
}
```

### Get Market Analysis

```bash
GET /v1/pricing/market-analysis
```

**Query Parameters:**
- `make` (required)
- `model` (required)
- `year` (required)
- `region` (optional)

**Response:**
```json
{
  "data": {
    "average_price": 46500.00,
    "median_price": 47000.00,
    "price_range": {
      "min": 42000.00,
      "max": 51000.00
    },
    "market_trend": "stable",
    "demand_level": "high",
    "time_on_market_days": 12,
    "comparable_listings": 45
  }
}
```

---

## Orders API

### Create Order

```bash
POST /v1/orders
```

**Request Body:**
```json
{
  "vehicle_id": "veh_123456789",
  "buyer_info": {
    "first_name": "Mario",
    "last_name": "Rossi",
    "email": "mario.rossi@example.com",
    "phone": "+39 123 456 7890",
    "fiscal_code": "RSSMRA80A01H501U"
  },
  "delivery": {
    "method": "pickup",
    "location_id": "loc_milan_001"
  },
  "payment": {
    "method": "financing",
    "down_payment": 10000.00
  },
  "notes": "Please contact me after 6 PM"
}
```

**Response:**
```json
{
  "data": {
    "order_id": "ord_987654321",
    "status": "pending_confirmation",
    "vehicle": {
      "id": "veh_123456789",
      "make": "BMW",
      "model": "X5",
      "price": 48700.00
    },
    "total_amount": 51200.00,
    "breakdown": {
      "vehicle_price": 48700.00,
      "registration_fee": 300.00,
      "delivery_fee": 0.00,
      "insurance": 1200.00,
      "vat": 1000.00
    },
    "created_at": "2024-01-15T12:00:00Z",
    "expires_at": "2024-01-18T12:00:00Z"
  }
}
```

### Get Order Status

```bash
GET /v1/orders/{order_id}
```

### Update Order

```bash
PATCH /v1/orders/{order_id}
```

**Request Body:**
```json
{
  "status": "confirmed",
  "notes": "Customer confirmed via phone"
}
```

### List Orders

```bash
GET /v1/orders
```

**Query Parameters:**
- `status`: Filter by status
- `date_from`: Start date (ISO 8601)
- `date_to`: End date (ISO 8601)
- `page`: Page number
- `per_page`: Items per page

---

## Payments API

### Create Payment Intent

```bash
POST /v1/payments/intent
```

**Request Body:**
```json
{
  "order_id": "ord_987654321",
  "amount": 51200.00,
  "currency": "EUR",
  "payment_method": "card",
  "installments": 1
}
```

**Response:**
```json
{
  "data": {
    "payment_intent_id": "pi_1234567890",
    "client_secret": "pi_1234567890_secret_xyz",
    "amount": 51200.00,
    "currency": "EUR",
    "status": "requires_confirmation",
    "payment_methods": ["card", "bank_transfer", "financing"]
  }
}
```

### Confirm Payment

```bash
POST /v1/payments/{payment_intent_id}/confirm
```

**Request Body:**
```json
{
  "payment_method_id": "pm_1234567890"
}
```

### Get Payment Status

```bash
GET /v1/payments/{payment_intent_id}
```

---

## Search API

### Full-Text Search

```bash
GET /v1/search
```

**Query Parameters:**
- `q`: Search query
- `filters`: JSON encoded filters
- `sort`: Sort field
- `page`, `per_page`: Pagination

**Example:**
```bash
curl -X GET "https://api.auto-broker.com/v1/search?q=BMW+X5+2023&filters=%7B%22price_max%22%3A50000%7D" \
  -H "Authorization: Bearer <token>"
```

**Response:**
```json
{
  "data": {
    "items": [...],
    "facets": {
      "make": [
        {"value": "BMW", "count": 156},
        {"value": "Mercedes", "count": 89}
      ],
      "fuel_type": [
        {"value": "diesel", "count": 120},
        {"value": "petrol", "count": 80}
      ]
    },
    "total": 156
  }
}
```

---

## Webhooks

### Register Webhook

```bash
POST /v1/webhooks
```

**Request Body:**
```json
{
  "url": "https://your-domain.com/webhook/auto-broker",
  "events": ["order.created", "order.status_changed", "payment.completed"],
  "secret": "your-webhook-secret",
  "is_active": true
}
```

### Webhook Events

| Event | Description |
|-------|-------------|
| `vehicle.created` | New vehicle added |
| `vehicle.updated` | Vehicle details changed |
| `vehicle.price_changed` | Vehicle price updated |
| `order.created` | New order placed |
| `order.status_changed` | Order status updated |
| `order.cancelled` | Order cancelled |
| `payment.completed` | Payment successful |
| `payment.failed` | Payment failed |

### Webhook Payload Example

```json
{
  "event": "order.status_changed",
  "timestamp": "2024-01-15T12:00:00Z",
  "data": {
    "order_id": "ord_987654321",
    "previous_status": "pending",
    "new_status": "confirmed",
    "changed_at": "2024-01-15T12:00:00Z",
    "changed_by": "system"
  }
}
```

### Webhook Signature Verification

```python
import hmac
import hashlib

def verify_webhook(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

---

## Rate Limiting

| Endpoint Type | Limit | Window |
|--------------|-------|--------|
| Authentication | 5 requests | 1 minute |
| General API | 100 requests | 1 minute |
| Search | 30 requests | 1 minute |
| Pricing | 60 requests | 1 minute |

**Rate Limit Headers:**
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1705321200
```

---

## SDK Examples

### Python

```python
import requests

class AutoBrokerClient:
    def __init__(self, api_key: str, base_url: str = "https://api.auto-broker.com/v1"):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def get_vehicles(self, **filters) -> dict:
        response = requests.get(
            f"{self.base_url}/vehicles",
            headers=self.headers,
            params=filters
        )
        response.raise_for_status()
        return response.json()
    
    def create_order(self, vehicle_id: str, buyer_info: dict) -> dict:
        response = requests.post(
            f"{self.base_url}/orders",
            headers=self.headers,
            json={
                "vehicle_id": vehicle_id,
                "buyer_info": buyer_info
            }
        )
        response.raise_for_status()
        return response.json()

# Usage
client = AutoBrokerClient(api_key="your-api-key")
vehicles = client.get_vehicles(make="BMW", price_max=50000)
```

### JavaScript/TypeScript

```typescript
class AutoBrokerClient {
  constructor(
    private apiKey: string,
    private baseUrl: string = "https://api.auto-broker.com/v1"
  ) {}

  async getVehicles(filters: Record<string, any> = {}): Promise<any> {
    const params = new URLSearchParams(filters);
    const response = await fetch(`${this.baseUrl}/vehicles?${params}`, {
      headers: {
        "Authorization": `Bearer ${this.apiKey}`,
        "Content-Type": "application/json"
      }
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return response.json();
  }

  async createOrder(vehicleId: string, buyerInfo: any): Promise<any> {
    const response = await fetch(`${this.baseUrl}/orders`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${this.apiKey}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        vehicle_id: vehicleId,
        buyer_info: buyerInfo
      })
    });
    
    return response.json();
  }
}

// Usage
const client = new AutoBrokerClient("your-api-key");
const vehicles = await client.getVehicles({ make: "BMW", price_max: 50000 });
```

---

## Error Codes

| Code | Description | Resolution |
|------|-------------|------------|
| `INVALID_REQUEST` | Malformed request | Check request format |
| `VALIDATION_ERROR` | Input validation failed | Check error details |
| `AUTHENTICATION_ERROR` | Invalid credentials | Renew token |
| `AUTHORIZATION_ERROR` | Insufficient permissions | Contact admin |
| `RESOURCE_NOT_FOUND` | Resource doesn't exist | Check resource ID |
| `RESOURCE_CONFLICT` | Resource already exists | Use different identifier |
| `RATE_LIMIT_EXCEEDED` | Too many requests | Wait and retry |
| `INTERNAL_ERROR` | Server error | Contact support |
| `SERVICE_UNAVAILABLE` | Service temporarily down | Retry with backoff |
| `TIMEOUT_ERROR` | Request timed out | Retry with longer timeout |

---

## Changelog

See [CHANGELOG.md](../CHANGELOG.md) for API version history.
