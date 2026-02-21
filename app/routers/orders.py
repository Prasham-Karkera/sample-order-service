from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import (
    InsufficientStockError,
    InvalidStatusTransitionError,
    OrderNotFoundError,
    UserValidationError,
)
from app.schemas.order import CreateOrderRequest, OrderResponse, UpdateOrderStatusRequest
from app.services.order_service import OrderService

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/v1/orders")


def _get_service(db: Annotated[AsyncSession, Depends(get_db)]) -> OrderService:
    return OrderService(db)


def _get_user_id(x_fleetbite_user_id: Annotated[str, Header(alias="x-fleetbite-user-id")]) -> uuid.UUID:
    """Extract authenticated user ID injected by the API Gateway."""
    return uuid.UUID(x_fleetbite_user_id)


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new order",
    description=(
        "Validates the user via user-service, checks stock via inventory-service, "
        "deducts stock, persists the order, and emits an ORDER_CREATED event to notification-service."
    ),
    operation_id="create_order",
    tags=["Orders"],
)
async def create_order(
    body: CreateOrderRequest,
    user_id: Annotated[uuid.UUID, Depends(_get_user_id)],
    svc: Annotated[OrderService, Depends(_get_service)],
) -> OrderResponse:
    try:
        return await svc.create_order(user_id, body)
    except UserValidationError as exc:
        raise HTTPException(status_code=422, detail={"error": {"code": "USER_VALIDATION_FAILED", "message": str(exc)}}) from exc
    except InsufficientStockError as exc:
        raise HTTPException(status_code=409, detail={"error": {"code": "INSUFFICIENT_STOCK", "message": str(exc)}}) from exc


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Get order by ID",
    operation_id="get_order",
    tags=["Orders"],
)
async def get_order(
    order_id: uuid.UUID,
    svc: Annotated[OrderService, Depends(_get_service)],
) -> OrderResponse:
    try:
        return await svc.get_order(order_id)
    except OrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error": {"code": "ORDER_NOT_FOUND", "message": str(exc)}}) from exc


@router.patch(
    "/{order_id}/status",
    response_model=OrderResponse,
    summary="Update order status",
    description="Transitions an order through its status FSM: PENDING → CONFIRMED → PREPARING → OUT_FOR_DELIVERY → DELIVERED.",
    operation_id="update_order_status",
    tags=["Orders"],
)
async def update_order_status(
    order_id: uuid.UUID,
    body: UpdateOrderStatusRequest,
    svc: Annotated[OrderService, Depends(_get_service)],
) -> OrderResponse:
    try:
        return await svc.update_status(order_id, body)
    except OrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error": {"code": "ORDER_NOT_FOUND", "message": str(exc)}}) from exc
    except InvalidStatusTransitionError as exc:
        raise HTTPException(status_code=409, detail={"error": {"code": "INVALID_STATUS_TRANSITION", "message": str(exc)}}) from exc
