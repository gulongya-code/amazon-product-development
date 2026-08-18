"""XLSX Operator Delivery Foundation V0.1 error hierarchy."""

from __future__ import annotations


class XlsxDeliveryError(Exception):
    """Base error for XLSX delivery."""


class XlsxDeliveryValidationError(XlsxDeliveryError, ValueError):
    """Raised when XLSX delivery data violates a V0.1 invariant."""


class XlsxDeliverySerializationError(XlsxDeliveryValidationError):
    """Raised when strict XLSX delivery serialization fails."""


__all__ = (
    "XlsxDeliveryError",
    "XlsxDeliveryValidationError",
    "XlsxDeliverySerializationError",
)
