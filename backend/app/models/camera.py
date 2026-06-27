"""
RetailFlow AI — CameraZone ORM Model

Defines the rectangular region of interest (ROI) for each counter's queue area.
The CV service reads these zones at startup to know where to count people.

Coordinate System:
    Pixel coordinates relative to the camera frame (top-left = 0,0).
    x1, y1 = top-left corner of zone
    x2, y2 = bottom-right corner of zone

    Example for a 1280×720 camera:
        zone covers the right third of the frame:
        x1=853, y1=0, x2=1280, y2=720

Counting Method:
    A person is counted as "in queue" if their foot centroid
    (bottom-center of YOLOv8 bounding box) falls within the zone rectangle.
    Using foot position (not body center) prevents double-counting people
    who are partially in and partially out of the zone.

One-to-one relationship:
    Each counter has at most ONE camera zone.
    A counter with no zone will have its queue updated manually only.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CameraSource(str, enum.Enum):
    """
    Camera source type.

    RTSP:       Real IP camera (e.g., rtsp://192.168.1.100/stream)
    USB:        Local USB/webcam (device index, e.g., "0")
    SIMULATION: Synthetic data (for demo/testing without hardware)
    """
    RTSP = "rtsp"
    USB = "usb"
    SIMULATION = "simulation"


class CameraZone(Base):
    """
    Defines the camera source and queue zone for a specific counter.

    The CV service processor polls this table at startup to configure
    one detection pipeline per active zone.
    """

    __tablename__ = "camera_zones"

    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Scope: which counter does this zone track?
    counter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("counters.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # One zone per counter
        index=True,
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Camera Source
    camera_source: Mapped[CameraSource] = mapped_column(
        String(20),
        nullable=False,
        default=CameraSource.SIMULATION,
    )
    camera_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="RTSP URL or USB device index. NULL for simulation mode.",
    )

    # Queue Zone Bounding Box (pixel coordinates)
    zone_x1: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Zone top-left X (pixels from camera frame left edge)",
    )
    zone_y1: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Zone top-left Y (pixels from camera frame top edge)",
    )
    zone_x2: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Zone bottom-right X",
    )
    zone_y2: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Zone bottom-right Y",
    )

    # Frame Dimensions (needed for coordinate normalization in the frontend)
    frame_width: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1280,
    )
    frame_height: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=720,
    )

    # Detection Config
    min_confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.45,
        comment="YOLOv8 confidence threshold (0.0–1.0). Lower = more detections, more noise.",
    )
    update_interval_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
        comment="How often (seconds) to push a new queue count to the Queue Engine",
    )

    # State
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<CameraZone counter={self.counter_id} "
            f"source={self.camera_source} zone=({self.zone_x1},{self.zone_y1},"
            f"{self.zone_x2},{self.zone_y2})>"
        )
