from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.database import engine
from app.models.order import Base
from app.routers import health, orders

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("order_service_starting", version=settings.APP_VERSION)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    logger.info("order_service_shutdown")
    await engine.dispose()


app = FastAPI(
    title="FleetBite Order Service",
    description="Manages order lifecycle: creation, status transitions, and event emission.",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.ENV != "production" else None,
    lifespan=lifespan,
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")
app.include_router(orders.router, tags=["Orders"])
app.include_router(health.router, tags=["Health"])
