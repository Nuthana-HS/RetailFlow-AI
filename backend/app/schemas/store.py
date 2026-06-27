"""
RetailFlow AI — Store & Counter Pydantic Schemas

Request and response schemas for the store management API.
All schemas follow the same design rules as auth.py:
  - Requests: validate at the boundary, strict types
  - Responses: never expose sensitive or internal fields
  - All times stored as strings (HH:MM) for API simplicity
"""

import uuid
from datetime import datetime, time
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.store import CounterStatus


# =============================================================================
# Store Request Schemas
# =============================================================================

class StoreCreateRequest(BaseModel):
    """Request body for POST /api/v1/stores."""

    name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        examples=["D-Mart Andheri West"],
        description="Store display name",
    )
    address: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Full street address",
        examples=["Lokhandwala Complex, Andheri West"],
    )
    city: str = Field(
        ...,
        min_length=2,
        max_length=100,
        examples=["Mumbai"],
    )
    state: str = Field(
        ...,
        min_length=2,
        max_length=100,
        examples=["Maharashtra"],
    )
    zip_code: str | None = Field(
        default=None,
        max_length=20,
        pattern=r"^\d{6}$",
        examples=["400053"],
        description="6-digit Indian postal code",
    )
    phone: str | None = Field(
        default=None,
        max_length=20,
        examples=["+91-22-6789-0123"],
    )
    open_time: str = Field(
        default="09:00",
        pattern=r"^\d{2}:\d{2}$",
        description="Daily opening time in HH:MM format (24-hour)",
        examples=["09:00"],
    )
    close_time: str = Field(
        default="22:00",
        pattern=r"^\d{2}:\d{2}$",
        description="Daily closing time in HH:MM format (24-hour)",
        examples=["22:00"],
    )
    avg_service_time: int = Field(
        default=180,
        ge=30,
        le=1800,
        description="Average seconds per customer checkout (30s–30min)",
    )

    @model_validator(mode="after")
    def validate_operating_hours(self) -> "StoreCreateRequest":
        """Ensure close_time is after open_time."""
        try:
            open_h, open_m = map(int, self.open_time.split(":"))
            close_h, close_m = map(int, self.close_time.split(":"))
            open_minutes = open_h * 60 + open_m
            close_minutes = close_h * 60 + close_m
            if close_minutes <= open_minutes:
                raise ValueError("close_time must be after open_time")
        except (ValueError, AttributeError) as e:
            if "must be after" in str(e):
                raise
        return self


class StoreUpdateRequest(BaseModel):
    """
    Request body for PATCH /api/v1/stores/{id}.
    All fields optional for partial updates.
    """

    name: str | None = Field(default=None, min_length=2, max_length=255)
    address: str | None = Field(default=None, min_length=5, max_length=500)
    city: str | None = Field(default=None, min_length=2, max_length=100)
    state: str | None = Field(default=None, min_length=2, max_length=100)
    zip_code: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=20)
    open_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    close_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    avg_service_time: int | None = Field(default=None, ge=30, le=1800)
    is_active: bool | None = None


class AssignManagerRequest(BaseModel):
    """Request body for POST /api/v1/stores/{id}/managers."""

    manager_id: uuid.UUID = Field(
        ...,
        description="UUID of the manager user to assign",
    )


# =============================================================================
# Counter Request Schemas
# =============================================================================

class CounterCreateRequest(BaseModel):
    """Request body for POST /api/v1/stores/{id}/counters."""

    counter_number: int = Field(
        ...,
        ge=1,
        le=99,
        description="Counter number displayed to customers (1–99)",
        examples=[5],
    )
    label: str | None = Field(
        default=None,
        max_length=100,
        description="Optional friendly label",
        examples=["Express Lane"],
    )
    status: CounterStatus = Field(
        default=CounterStatus.CLOSED,
        description="Initial counter status",
    )


class CounterUpdateRequest(BaseModel):
    """
    Request body for PATCH /api/v1/counters/{id}.
    All fields optional.
    """

    label: str | None = Field(default=None, max_length=100)
    status: CounterStatus | None = None
    cashier_id: uuid.UUID | None = None


# =============================================================================
# Response Schemas
# =============================================================================

class ManagerSummary(BaseModel):
    """Compact manager profile for inclusion in store responses."""

    id: uuid.UUID
    full_name: str
    email: str

    model_config = {"from_attributes": True}


class CashierSummary(BaseModel):
    """Compact cashier profile for inclusion in counter responses."""

    id: uuid.UUID
    full_name: str

    model_config = {"from_attributes": True}


class CounterResponse(BaseModel):
    """Full counter details returned in API responses."""

    id: uuid.UUID
    store_id: uuid.UUID
    counter_number: int
    label: str | None
    status: CounterStatus
    cashier: CashierSummary | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "use_enum_values": True}


class StoreResponse(BaseModel):
    """Full store details returned in API responses."""

    id: uuid.UUID
    name: str
    address: str
    city: str
    state: str
    zip_code: str | None
    phone: str | None
    open_time: str       # Serialized as "HH:MM" string
    close_time: str
    avg_service_time: int
    is_active: bool
    admin_id: uuid.UUID
    counter_count: int = Field(default=0, description="Total number of active counters")
    open_counter_count: int = Field(default=0, description="Currently open counters")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_store(cls, store: object, counter_count: int = 0, open_counter_count: int = 0) -> "StoreResponse":
        """Build StoreResponse from a Store ORM instance."""
        from app.models.store import Store as StoreModel
        s: StoreModel = store  # type: ignore[assignment]
        return cls(
            id=s.id,
            name=s.name,
            address=s.address,
            city=s.city,
            state=s.state,
            zip_code=s.zip_code,
            phone=s.phone,
            open_time=s.open_time.strftime("%H:%M"),
            close_time=s.close_time.strftime("%H:%M"),
            avg_service_time=s.avg_service_time,
            is_active=s.is_active,
            admin_id=s.admin_id,
            counter_count=counter_count,
            open_counter_count=open_counter_count,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )


class StoreDetailResponse(StoreResponse):
    """Detailed store response including managers and counters lists."""

    managers: list[ManagerSummary] = []
    counters: list[CounterResponse] = []


class StoreListItem(BaseModel):
    """Compact store item for list responses."""

    id: uuid.UUID
    name: str
    city: str
    state: str
    is_active: bool
    counter_count: int
    open_counter_count: int

    model_config = {"from_attributes": True}


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""

    total: int
    page: int
    limit: int
    pages: int


class StoreListResponse(BaseModel):
    """Paginated store list response."""

    items: list[StoreResponse]
    meta: PaginationMeta
