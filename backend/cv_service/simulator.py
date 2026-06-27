"""
RetailFlow AI — Frame Simulator

Generates synthetic frames and detections for testing the CV pipeline
without a physical camera or YOLOv8 model.

Two simulation modes:

1. DETECTION-LEVEL simulation (preferred for unit tests):
   FrameSimulator.generate_detections() returns a list of Detection objects
   with randomized positions, bypassing the YOLOv8 model entirely.
   Used by FrameProcessor when camera_source=SIMULATION.

2. FRAME-LEVEL simulation (for integration/visual tests):
   FrameSimulator.generate_frame() returns a blank numpy array that
   can be passed to PersonDetector.detect() (though YOLOv8 will find nothing
   in a blank frame — useful for testing the pipeline without crashes).

Realistic Queue Simulation:
   The detection generator uses a simple random walk with momentum:
   - Queue length trends up during "busy" periods and down during "quiet" periods
   - People positions are scattered within realistic zone areas
   - This produces believable time-series data for analytics testing
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timezone

import numpy as np

from cv_service.detector import Detection
from cv_service.zone_counter import QueueZone


class FrameSimulator:
    """
    Generates synthetic queue data without real hardware.

    Used when camera_source = CameraSource.SIMULATION.
    """

    def __init__(
        self,
        zone: QueueZone,
        max_queue: int = 15,
        seed: int | None = None,
    ) -> None:
        """
        Args:
            zone: The zone to simulate detections within.
            max_queue: Maximum simulated queue length.
            seed: Random seed for reproducible tests.
        """
        self.zone = zone
        self.max_queue = max_queue
        self._rng = random.Random(seed)
        self._current_queue = 0
        self._momentum = 0  # Trend: positive = growing, negative = shrinking

    def generate_detections(self) -> list[Detection]:
        """
        Generate synthetic detections within the zone.

        Uses a random walk with momentum to simulate realistic queue dynamics:
          - Queue grows during simulated rush hour
          - Queue shrinks as counters serve customers
          - Small random noise on each frame

        Returns:
            List of synthetic Detection objects positioned within the zone.
        """
        # Update momentum (creates gradual trends)
        self._momentum += self._rng.randint(-2, 2)
        self._momentum = max(-3, min(3, self._momentum))  # Clamp

        # Update queue length
        self._current_queue += self._momentum
        self._current_queue = max(0, min(self.max_queue, self._current_queue))

        # Generate person detections within the zone
        detections = []
        for _ in range(self._current_queue):
            cx = self._rng.uniform(self.zone.x1 + 10, self.zone.x2 - 10)
            cy = self._rng.uniform(self.zone.y1 + 50, self.zone.y2 - 10)
            # Typical person bounding box: ~50px wide, ~150px tall
            half_w = self._rng.uniform(20, 30)
            half_h = self._rng.uniform(60, 80)
            detections.append(
                Detection(
                    x1=cx - half_w,
                    y1=cy - half_h * 2,  # Head is above feet
                    x2=cx + half_w,
                    y2=cy,  # cy = bottom of box = feet
                    confidence=self._rng.uniform(0.50, 0.99),
                )
            )

        return detections

    def generate_frame(self) -> np.ndarray:
        """
        Generate a blank synthetic video frame (H×W×3 BGR numpy array).

        YOLOv8 will find no people in a blank frame.
        Used only for pipeline smoke tests.

        Returns:
            Zero-filled numpy array of shape (frame_height, frame_width, 3).
        """
        return np.zeros(
            (self.zone.frame_height, self.zone.frame_width, 3),
            dtype=np.uint8,
        )

    @property
    def current_queue_length(self) -> int:
        """Current simulated queue length (for debugging/tests)."""
        return self._current_queue

    def reset(self) -> None:
        """Reset the simulator to initial state."""
        self._current_queue = 0
        self._momentum = 0
