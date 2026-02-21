from __future__ import annotations

import uuid
from decimal import Decimal

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.exceptions import (
    InsufficientStockError,
    InvalidStatusTransitionError,
    OrderNotFoundError,
    UserValidationError,
)
from app.models.order import Order, OrderItem, OrderStatus
from app.schemas.order import CreateOrderRequest, OrderResponse, UpdateOrderStatusRequest

logger = structlog.get_logger(__name__)


class InventoryItemInfo:
    def __init__(self, item_id: uuid.UUID, name: str, price: Decimal, stock: int) -> None:
        self.item_id = item_id
        self.name = name
        self.price = price
        self.stock = stock


class OrderService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def _validate_user(self, user_id: uuid.UUID) -> None:
        """Check user-service that user exists and is active."""
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
            resp = await client.get(f"{settings.USER_SERVICE_URL}/v1/users/{user_id}")
        if resp.status_code == 404:
            raise UserValidationError(f"User {user_id} not found in user-service")
        resp.raise_for_status()
        user_data = resp.json()
        if not user_data.get("is_active", False):
            raise UserValidationError(f"User {user_id} is inactive")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def _fetch_item_info(self, item_id: uuid.UUID) -> InventoryItemInfo:
        """Fetch item details and stock level from inventory-service."""
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
            item_resp = await client.get(f"{settings.INVENTORY_SERVICE_URL}/v1/items/{item_id}")
            stock_resp = await client.get(f"{settings.INVENTORY_SERVICE_URL}/v1/stock/{item_id}")
        item_resp.raise_for_status()
        stock_resp.raise_for_status()
        item = item_resp.json()["data"]
        stock = stock_resp.json()["data"]
        return InventoryItemInfo(
            item_id=uuid.UUID(item["id"]),
            name=item["name"],
            price=Decimal(str(item["price"])),
            stock=stock["quantity"],
        )

    async def _deduct_stock(self, item_id: uuid.UUID, quantity: int) -> None:
        """Call inventory-service to deduct stock."""
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
            resp = await client.post(
                f"{settings.INVENTORY_SERVICE_URL}/v1/stock/deduct",
                json={"item_id": str(item_id), "quantity": quantity},
            )
        resp.raise_for_status()

    async def _emit_order_event(self, order: Order, event_type: str) -> None:
        """Fire-and-forget event to notification-service."""
        payload = {
            "event_type": event_type,
            "source": "order-service",
            "payload": {
                "order_id": str(order.id),
                "user_id": str(order.user_id),
                "status": order.status.value,
                "total_amount": str(order.total_amount),
            },
        }
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                await client.post(f"{settings.NOTIFICATION_SERVICE_URL}/v1/events", json=payload)
        except Exception as exc:
            # Non-critical; log and continue
            logger.warning("notification_event_failed", event_type=event_type, error=str(exc))

    async def create_order(self, user_id: uuid.UUID, request: CreateOrderRequest) -> OrderResponse:
        await self._validate_user(user_id)

        order_items: list[OrderItem] = []
        total_amount = Decimal("0.00")

        for line in request.items:
            info = await self._fetch_item_info(line.item_id)
            if info.stock < line.quantity:
                raise InsufficientStockError(
                    f"Insufficient stock for item {line.item_id}: "
                    f"requested {line.quantity}, available {info.stock}"
                )
            subtotal = info.price * line.quantity
            total_amount += subtotal
            order_items.append(
                OrderItem(
                    item_id=line.item_id,
                    item_name=info.name,
                    quantity=line.quantity,
                    unit_price=info.price,
                )
            )

        order = Order(
            user_id=user_id,
            total_amount=total_amount,
            delivery_address=request.delivery_address,
            notes=request.notes,
            items=order_items,
        )
        self._db.add(order)

        # Deduct stock in inventory-service
        for line in request.items:
            await self._deduct_stock(line.item_id, line.quantity)

        await self._db.commit()
        await self._db.refresh(order)

        logger.info("order_created", order_id=str(order.id), user_id=str(user_id), total=str(total_amount))
        await self._emit_order_event(order, "ORDER_CREATED")
        return OrderResponse.model_validate(order)

    async def update_status(self, order_id: uuid.UUID, request: UpdateOrderStatusRequest) -> OrderResponse:
        result = await self._db.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            raise OrderNotFoundError(f"Order {order_id} not found")

        if not order.can_transition_to(request.status):
            raise InvalidStatusTransitionError(
                f"Cannot transition from {order.status.value} to {request.status.value}"
            )

        old_status = order.status
        order.status = request.status
        await self._db.commit()
        await self._db.refresh(order)

        logger.info("order_status_updated", order_id=str(order_id), from_status=old_status, to_status=request.status)
        await self._emit_order_event(order, f"ORDER_{request.status.value}")
        return OrderResponse.model_validate(order)

    async def get_order(self, order_id: uuid.UUID) -> OrderResponse:
        result = await self._db.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            raise OrderNotFoundError(f"Order {order_id} not found")
        return OrderResponse.model_validate(order)
