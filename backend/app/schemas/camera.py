"""
RetailFlow AI — Camera Zone Pydantic Schemas
"""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, model_validator

from app.models.camera import CameraSource


class CameraZoneRequest(BaseModel):
    """Request body for creating or updating a camera zone."""

    camera_source: CameraSource = Field(
        default=CameraSource.SIMULATION,
        description="Camera source: 'rtsp', 'usb', or 'simulation'",
    )
    camera_url: str | None = Field(
        default=None,
        max_length=500,
        description="RTSP URL (e.g., rtsp://192.168.1.100/stream). Required if source=rtsp.",
        examples=["rtsp://admin:pass@192.168.1.100:554/stream"],
    )

    # Zone coordinates (pixel space)
    zone_x1: float = Field(..., ge=0, description="Zone top-left X (pixels)")
    zone_y1: float = Field(..., ge=0, description="Zone top-left Y (pixels)")
    zone_x2: float = Field(..., ge=0, description="Zone bottom-right X (pixels)")
    zone_y2: float = Field(..., ge=0, description="Zone bottom-right Y (pixels)")

    # Frame dimensions
    frame_width: int = Field(default=1280, ge=100, le=7680)
    frame_height: int = Field(default=720, ge=100, le=4320)

    # Detection config
    min_confidence: float = Field(
        default=0.45,
        ge=0.1,
        le=0.95,
        description="YOLOv8 detection confidence threshold",
    )
    update_interval_seconds: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Queue update frequency in seconds (1–60)",
    )
    is_active: bool = Field(default=True)

    @model_validator(mode="after")
    def validate_zone_coordinates(self) -> "CameraZoneRequest":
        """Ensure x2 > x1 and y2 > y1 (valid bounding box)."""
        if self.zone_x2 <= self.zone_x1:
            raise ValueError("zone_x2 must be greater than zone_x1")
        if self.zone_y2 <= self.zone_y1:
            raise ValueError("zone_y2 must be greater than zone_y1")
        if self.camera_source == CameraSource.RTSP and not self.camera_url:
            raise ValueError("camera_url is required when camera_source is 'rtsp'")
        return self


class CameraZoneResponse(BaseModel):
    """Camera zone returned in API responses."""

    id: uuid.UUID
    counter_id: uuid.UUID
    store_id: uuid.UUID
    camera_source: CameraSource
    camera_url: str | None
    zone_x1: float
    zone_y1: float
    zone_x2: float
    zone_y2: float
    frame_width: int
    frame_height: int
    min_confidence: float
    update_interval_seconds: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "use_enum_values": True}
