from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.order import OrderStatus


class OrderItemRequest(BaseModel):
    item_id: uuid.UUID = Field(..., description="Inventory item UUID")
    quantity: int = Field(..., ge=1, description="Must be ≥ 1", example=2)


class CreateOrderRequest(BaseModel):
    items: list[OrderItemRequest] = Field(..., min_length=1)
    delivery_address: str = Field(..., min_length=5, example="42 MG Road, Bengaluru 560001")
    notes: str | None = Field(default=None, example="Extra spicy please")


class UpdateOrderStatusRequest(BaseModel):
    status: OrderStatus = Field(..., description="New order status")


class OrderItemResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    item_id: uuid.UUID
    item_name: str
    quantity: int
    unit_price: Decimal


class OrderResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    user_id: uuid.UUID
    status: OrderStatus
    total_amount: Decimal
    delivery_address: str
    notes: str | None
    items: list[OrderItemResponse]
    created_at: datetime
    updated_at: datetime
