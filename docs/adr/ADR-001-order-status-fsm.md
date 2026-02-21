# ADR-001: Order Status as Finite State Machine

**Status:** ACCEPTED  
**Date:** 2026-01-20  
**Author(s):** @prasham-dev  
**Deciders:** @prasham-dev, @backend-lead  

---

## Context

Orders have a lifecycle with multiple states. We needed to decide how to model and enforce valid state transitions to prevent invalid states like an order going from CANCELLED back to CONFIRMED.

## Decision

Model order status as an **explicit Finite State Machine (FSM)** directly on the `Order` ORM model, with a `VALID_TRANSITIONS` dict and a `can_transition_to()` method.

## Rationale

### Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| FSM on model | Self-documenting, enforced at domain layer | Slightly more code | ✅ Selected |
| Ad-hoc in service layer | Simple | Not enforced at domain, easy to bypass | ❌ Rejected |
| External state machine lib | Rich features | Over-engineering for 6 states | ❌ Rejected |

## Consequences

- All status transitions must call `order.can_transition_to(new_status)` before updating
- API returns HTTP 409 for invalid transitions with clear error code `INVALID_STATUS_TRANSITION`
- Valid transitions: `PENDING → CONFIRMED → PREPARING → OUT_FOR_DELIVERY → DELIVERED`; `PENDING/CONFIRMED → CANCELLED`

## ADR-002: Synchronous vs Async Downstream Calls

**Status:** ACCEPTED  
**Date:** 2026-01-22  

## Context

When creating an order, we call user-service (validate user), inventory-service (check stock, deduct), and notification-service (emit event). Should these be sync HTTP calls or async via a message queue?

## Decision

Use **synchronous HTTP** for user validation and inventory operations. Use **fire-and-forget HTTP** for notifications with graceful degradation.

## Rationale

- User validation and stock deduction are **critical path** — the order cannot be created without them
- Notifications are **non-critical** — a failed notification event should not fail the order creation
- Message queue (Kafka/RabbitMQ) adds operational complexity not justified at current scale

**Trade-off:** Synchronous calls add latency and coupling. At scale (>100 orders/sec), migrate to async event bus.
