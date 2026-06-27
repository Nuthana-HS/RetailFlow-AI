"""
RetailFlow AI — Queue Zone Counter

Counts how many detected people are "in queue" within a defined zone.

Zone Assignment Algorithm:
    For each detected person, check if their FOOT CENTROID (cx, cy)
    falls within the zone's bounding rectangle [x1, y1, x2, y2].

    A person is "in queue" if:
        zone.x1 <= detection.cx <= zone.x2
        AND
        zone.y1 <= detection.cy <= zone.y2

Why foot centroid (bottom-center of bounding box)?
    - Avoids double-counting people standing at zone boundaries
    - Aligns with physical queue positioning (where someone IS = where they stand)
    - More stable than body center (less affected by pose/occlusion)

Multiple Zone Support:
    The zone_counter operates on a single zone per call.
    The processor.py iterates over zones for multi-counter stores.
"""

from __future__ import annotations

from dataclasses import dataclass

from cv_service.detector import Detection


@dataclass(frozen=True)
class QueueZone:
    """
    Rectangular zone of interest within a camera frame.

    Coordinates are in absolute pixels (same space as Detection coordinates).
    This is a value object — immutable and equality-comparable.
    """

    counter_id: str
    store_id: str
    x1: float
    y1: float
    x2: float
    y2: float
    frame_width: int = 1280
    frame_height: int = 720

    def __post_init__(self) -> None:
        if self.x2 <= self.x1:
            raise ValueError(f"Invalid zone: x2 ({self.x2}) must be > x1 ({self.x1})")
        if self.y2 <= self.y1:
            raise ValueError(f"Invalid zone: y2 ({self.y2}) must be > y1 ({self.y1})")

    @property
    def area(self) -> float:
        """Zone area in square pixels."""
        return (self.x2 - self.x1) * (self.y2 - self.y1)

    @property
    def coverage_percent(self) -> float:
        """What percentage of the frame this zone covers."""
        frame_area = self.frame_width * self.frame_height
        return round((self.area / frame_area) * 100, 2) if frame_area > 0 else 0.0

    def contains(self, detection: Detection) -> bool:
        """
        Check if a detection's foot centroid is within this zone.

        Args:
            detection: A single person detection from YOLOv8.

        Returns:
            True if the person's foot position is inside this zone.
        """
        return (
            self.x1 <= detection.cx <= self.x2
            and self.y1 <= detection.cy <= self.y2
        )

    def __repr__(self) -> str:
        return (
            f"QueueZone(counter={self.counter_id[:8]}... "
            f"({self.x1:.0f},{self.y1:.0f})→({self.x2:.0f},{self.y2:.0f}) "
            f"{self.coverage_percent:.1f}% of frame)"
        )


class ZoneCounter:
    """
    Counts people within a specific zone from a list of detections.

    Stateless — can be called multiple times with different detection sets.
    No memory of previous frames (tracking is intentionally out of scope;
    we count occupancy, not individual movement).

    Usage:
        counter = ZoneCounter()
        count = counter.count(detections, zone)
        in_zone = counter.filter(detections, zone)
    """

    def count(self, detections: list[Detection], zone: QueueZone) -> int:
        """
        Count the number of people in a zone.

        Args:
            detections: All detections in the current frame.
            zone: The zone to count within.

        Returns:
            Integer count of people in queue.
        """
        return sum(1 for det in detections if zone.contains(det))

    def filter(self, detections: list[Detection], zone: QueueZone) -> list[Detection]:
        """
        Return only detections that fall within the zone.

        Useful for visualization (drawing bounding boxes for in-zone people).

        Args:
            detections: All detections in the current frame.
            zone: The zone to filter by.

        Returns:
            Subset of detections inside the zone.
        """
        return [det for det in detections if zone.contains(det)]

    def count_multiple_zones(
        self,
        detections: list[Detection],
        zones: list[QueueZone],
    ) -> dict[str, int]:
        """
        Count people in multiple zones simultaneously.

        Returns:
            Dict of {counter_id: count} for all provided zones.

        Note on overlapping zones:
            If a person's foot centroid falls within multiple overlapping zones,
            they will be counted in EACH zone independently.
            Zone designers should ensure zones don't overlap significantly.
        """
        return {zone.counter_id: self.count(detections, zone) for zone in zones}
