# ka-chow-order-service

> **Service:** Order Processing  
> **Port:** 8001  
> **Team:** Commerce  
> **Database:** `fb_orders` (PostgreSQL)

## Service Overview

Manages the full lifecycle of customer orders — from creation through delivery. Orchestrates calls to user-service (user validation), inventory-service (stock checks and deduction), and notification-service (event emission). Enforces an explicit Finite State Machine for order status transitions.

## Architecture Role

```
API Gateway → [Order Service :8002] → user-service    (validate user)
                      │            → inventory-service (check/deduct stock)
                      │            → notification-service (ORDER_* events)
                      └──────────→ PostgreSQL (fb_orders)
```

## Dependencies

| Service | Purpose |
|---------|---------|
| user-service | Validate user exists and is active |
| inventory-service | Check stock availability, deduct on order creation |
| notification-service | Emit ORDER_CREATED, ORDER_CONFIRMED, etc. events |

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/orders` | Create order |
| `GET` | `/v1/orders/{id}` | Get order |
| `PATCH` | `/v1/orders/{id}/status` | Transition status |

### Order Status FSM

```
PENDING → CONFIRMED → PREPARING → OUT_FOR_DELIVERY → DELIVERED
    └──→ CANCELLED ←──┘
```

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `ORD_DATABASE_URL` | ✅ | PostgreSQL DSN |
| `ORD_JWT_SECRET_KEY` | ✅ | Must match gateway |
| `ORD_USER_SERVICE_URL` | — | Default: `http://user-service:8001` |
| `ORD_INVENTORY_SERVICE_URL` | — | Default: `http://inventory-service:8003` |
| `ORD_NOTIFICATION_SERVICE_URL` | — | Default: `http://notification-service:8004` |
| `ORD_HTTP_TIMEOUT` | — | Default: `5.0` |

## Running Locally

```bash
cp .env.example .env
docker-compose up -d
curl http://localhost:8002/health/live
```

## Running Tests

```bash
pip install -e ".[dev]"
pytest --cov=app tests/
```
