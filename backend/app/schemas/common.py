"""
RetailFlow AI — Common Pydantic Schemas

Defines the standard API response envelope used by ALL endpoints.
Enforces consistent response structure across the entire API.
"""

from datetime import datetime, timezone
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

# Generic type variable for the data payload
DataT = TypeVar("DataT")


# =============================================================================
# Standard API Response Envelope
# =============================================================================

class APIResponse(BaseModel, Generic[DataT]):
    """
    Standard response envelope for all API endpoints.

    Every endpoint returns either:
        APIResponse[SomeSchema]  → Success
        APIErrorResponse         → Error (see below)

    Example success:
        {
          "success": true,
          "data": { ... },
          "message": "User registered successfully",
          "timestamp": "2026-06-26T17:00:00Z"
        }
    """

    success: bool = True
    data: DataT
    message: str = "Success"
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="Response timestamp in UTC ISO 8601",
    )

    model_config = {"from_attributes": True}


class APIErrorDetail(BaseModel):
    """Individual field-level validation error."""
    field: str = Field(description="Field that failed validation")
    message: str = Field(description="Human-readable error message")


class APIErrorResponse(BaseModel):
    """
    Standard error response envelope.

    Example:
        {
          "success": false,
          "error": {
            "code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": [
              { "field": "email", "message": "Invalid email format" }
            ]
          },
          "timestamp": "2026-06-26T17:00:00Z"
        }
    """

    success: bool = False
    error: dict[str, object]
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )


class PaginatedResponse(BaseModel, Generic[DataT]):
    """Response envelope for paginated list endpoints."""

    success: bool = True
    data: dict[str, object]  # Contains items, total, page, limit, pages
    message: str = "Success"
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )

    model_config = {"from_attributes": True}
