from __future__ import annotations


class FleetBiteError(Exception):
    pass


class OrderNotFoundError(FleetBiteError):
    pass


class UserValidationError(FleetBiteError):
    pass


class InsufficientStockError(FleetBiteError):
    pass


class InvalidStatusTransitionError(FleetBiteError):
    pass
