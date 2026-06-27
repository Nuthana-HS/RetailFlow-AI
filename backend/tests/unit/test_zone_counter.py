"""
RetailFlow AI — Unit Tests: Zone Counter

Tests for ZoneCounter and QueueZone logic — the mathematical heart of the CV service.
No camera, YOLOv8, or network required.

Coverage:
  - QueueZone validation (x2 > x1, y2 > y1)
  - QueueZone.contains() with all edge cases
  - ZoneCounter.count() with various detection layouts
  - ZoneCounter.filter() returns correct subset
  - ZoneCounter.count_multiple_zones() for multi-counter stores
  - FrameSimulator generates in-zone detections
"""

import pytest

from cv_service.detector import Detection
from cv_service.zone_counter import QueueZone, ZoneCounter


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def standard_zone() -> QueueZone:
    """A 300×400 px zone in the center of a 1280×720 frame."""
    return QueueZone(
        counter_id="counter-001",
        store_id="store-abc",
        x1=200.0,
        y1=100.0,
        x2=500.0,
        y2=500.0,
        frame_width=1280,
        frame_height=720,
    )


def make_detection(cx: float, cy: float, conf: float = 0.90) -> Detection:
    """Helper: create a Detection whose foot centroid is at (cx, cy)."""
    return Detection(
        x1=cx - 25,
        y1=cy - 150,  # Head above feet
        x2=cx + 25,
        y2=cy,        # cy = bottom of box = foot position
        confidence=conf,
    )


# =============================================================================
# Test: QueueZone validation
# =============================================================================

class TestQueueZoneValidation:

    def test_valid_zone_creates_successfully(self) -> None:
        zone = QueueZone("c1", "s1", x1=0, y1=0, x2=100, y2=100)
        assert zone.x1 == 0
        assert zone.x2 == 100

    def test_invalid_zone_x2_le_x1_raises(self) -> None:
        """x2 must be strictly greater than x1."""
        with pytest.raises(ValueError, match="x2"):
            QueueZone("c1", "s1", x1=100, y1=0, x2=100, y2=100)  # x2 == x1

    def test_invalid_zone_x2_lt_x1_raises(self) -> None:
        with pytest.raises(ValueError, match="x2"):
            QueueZone("c1", "s1", x1=200, y1=0, x2=100, y2=100)  # x2 < x1

    def test_invalid_zone_y2_le_y1_raises(self) -> None:
        """y2 must be strictly greater than y1."""
        with pytest.raises(ValueError, match="y2"):
            QueueZone("c1", "s1", x1=0, y1=100, x2=100, y2=100)  # y2 == y1

    def test_zone_area(self) -> None:
        """Area = width × height."""
        zone = QueueZone("c1", "s1", x1=0, y1=0, x2=100, y2=200)
        assert zone.area == 20_000.0

    def test_zone_coverage_percent(self) -> None:
        """Coverage = zone area / frame area × 100."""
        # Zone covers exactly 1/4 of a 100×100 frame
        zone = QueueZone("c1", "s1", x1=0, y1=0, x2=50, y2=50,
                         frame_width=100, frame_height=100)
        assert zone.coverage_percent == 25.0


# =============================================================================
# Test: QueueZone.contains()
# =============================================================================

class TestZoneContains:

    def test_detection_inside_zone_returns_true(self, standard_zone: QueueZone) -> None:
        """Foot at center of zone is inside."""
        det = make_detection(cx=350.0, cy=300.0)  # Center of zone
        assert standard_zone.contains(det) is True

    def test_detection_outside_zone_returns_false(self, standard_zone: QueueZone) -> None:
        """Foot clearly outside zone is not counted."""
        det = make_detection(cx=600.0, cy=300.0)  # Right of zone (x2=500)
        assert standard_zone.contains(det) is False

    def test_detection_at_left_boundary_included(self, standard_zone: QueueZone) -> None:
        """Foot exactly at x1 boundary is included (inclusive)."""
        det = make_detection(cx=200.0, cy=300.0)  # cx == x1
        assert standard_zone.contains(det) is True

    def test_detection_at_right_boundary_included(self, standard_zone: QueueZone) -> None:
        """Foot exactly at x2 boundary is included (inclusive)."""
        det = make_detection(cx=500.0, cy=300.0)  # cx == x2
        assert standard_zone.contains(det) is True

    def test_detection_at_top_boundary_included(self, standard_zone: QueueZone) -> None:
        """Foot exactly at y1 boundary is included."""
        det = make_detection(cx=350.0, cy=100.0)  # cy == y1
        assert standard_zone.contains(det) is True

    def test_detection_at_bottom_boundary_included(self, standard_zone: QueueZone) -> None:
        """Foot exactly at y2 boundary is included."""
        det = make_detection(cx=350.0, cy=500.0)  # cy == y2
        assert standard_zone.contains(det) is True

    def test_detection_above_zone_returns_false(self, standard_zone: QueueZone) -> None:
        """Foot above zone top (cy < y1) is not counted."""
        det = make_detection(cx=350.0, cy=50.0)  # cy < y1=100
        assert standard_zone.contains(det) is False

    def test_detection_below_zone_returns_false(self, standard_zone: QueueZone) -> None:
        """Foot below zone bottom is not counted."""
        det = make_detection(cx=350.0, cy=600.0)  # cy > y2=500
        assert standard_zone.contains(det) is False


# =============================================================================
# Test: ZoneCounter
# =============================================================================

class TestZoneCounter:

    def test_count_zero_when_no_detections(self, standard_zone: QueueZone) -> None:
        """Empty detection list → 0 count."""
        counter = ZoneCounter()
        assert counter.count([], standard_zone) == 0

    def test_count_all_inside(self, standard_zone: QueueZone) -> None:
        """All detections inside zone → count equals len(detections)."""
        counter = ZoneCounter()
        dets = [make_detection(350, 300), make_detection(280, 400), make_detection(450, 200)]
        assert counter.count(dets, standard_zone) == 3

    def test_count_some_inside(self, standard_zone: QueueZone) -> None:
        """Mix of inside and outside detections."""
        counter = ZoneCounter()
        inside = [make_detection(350, 300), make_detection(280, 400)]
        outside = [make_detection(600, 300), make_detection(100, 300)]
        assert counter.count(inside + outside, standard_zone) == 2

    def test_count_all_outside(self, standard_zone: QueueZone) -> None:
        """All detections outside zone → 0."""
        counter = ZoneCounter()
        dets = [make_detection(600, 300), make_detection(100, 300)]
        assert counter.count(dets, standard_zone) == 0

    def test_filter_returns_only_inside_detections(self, standard_zone: QueueZone) -> None:
        """filter() returns subset of detections inside the zone."""
        counter = ZoneCounter()
        inside = make_detection(350, 300)
        outside = make_detection(900, 300)
        result = counter.filter([inside, outside], standard_zone)
        assert len(result) == 1
        assert result[0] is inside

    def test_count_multiple_zones(self) -> None:
        """count_multiple_zones() returns dict keyed by counter_id."""
        counter = ZoneCounter()
        zone_a = QueueZone("counter-a", "store-1", 0, 0, 300, 720)
        zone_b = QueueZone("counter-b", "store-1", 300, 0, 640, 720)

        # 2 people in zone A, 1 in zone B
        dets = [
            make_detection(100, 400),   # In A
            make_detection(200, 400),   # In A
            make_detection(400, 400),   # In B
        ]

        result = counter.count_multiple_zones(dets, [zone_a, zone_b])
        assert result["counter-a"] == 2
        assert result["counter-b"] == 1


# =============================================================================
# Test: FrameSimulator
# =============================================================================

class TestFrameSimulator:

    def test_simulator_detections_are_within_zone(self, standard_zone: QueueZone) -> None:
        """Simulated detections should all be inside their zone."""
        from cv_service.simulator import FrameSimulator
        from cv_service.zone_counter import ZoneCounter

        sim = FrameSimulator(zone=standard_zone, seed=42)
        counter = ZoneCounter()

        # Run 10 simulation cycles
        for _ in range(10):
            dets = sim.generate_detections()
            total = len(dets)
            in_zone = counter.count(dets, standard_zone)
            # All simulated detections should be within the zone
            assert in_zone == total, (
                f"Expected all {total} detections in zone, but only {in_zone} were"
            )

    def test_simulator_queue_length_bounded(self, standard_zone: QueueZone) -> None:
        """Simulated queue should never exceed max_queue."""
        from cv_service.simulator import FrameSimulator

        max_q = 5
        sim = FrameSimulator(zone=standard_zone, max_queue=max_q, seed=123)

        for _ in range(50):
            dets = sim.generate_detections()
            assert len(dets) <= max_q

    def test_simulator_generates_numpy_frame(self, standard_zone: QueueZone) -> None:
        """generate_frame() returns a numpy array of correct shape."""
        import numpy as np
        from cv_service.simulator import FrameSimulator

        sim = FrameSimulator(zone=standard_zone)
        frame = sim.generate_frame()
        assert isinstance(frame, np.ndarray)
        assert frame.shape == (standard_zone.frame_height, standard_zone.frame_width, 3)
