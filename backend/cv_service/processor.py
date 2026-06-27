"""
RetailFlow AI — CV Frame Processor

The main processing pipeline for a single camera zone.

Per-Zone Pipeline (runs in an asyncio task):
    ┌──────────────┐
    │ Frame Source │  Camera (RTSP/USB) or Simulator
    └──────┬───────┘
           │ frame (np.ndarray)
           ▼
    ┌──────────────┐
    │  PersonDetector │  YOLOv8-nano inference (or simulation)
    └──────┬───────┘
           │ detections (list[Detection])
           ▼
    ┌──────────────┐
    │  ZoneCounter │  foot-centroid containment check
    └──────┬───────┘
           │ queue_length (int)
           ▼
    ┌──────────────┐
    │ QueueUpdater │  POST /api/v1/queues/.../update  (source=cv)
    └──────────────┘

One FrameProcessor instance per camera zone.
All instances run as concurrent asyncio tasks in main.py.

OpenCV Dependency:
    Real camera capture uses cv2.VideoCapture (OpenCV).
    If OpenCV is not installed, simulation mode is always used.
"""

from __future__ import annotations

import asyncio
import logging
from enum import Enum

from cv_service.zone_counter import QueueZone, ZoneCounter

logger = logging.getLogger(__name__)


class SourceMode(str, Enum):
    REAL = "real"
    SIMULATION = "simulation"


class FrameProcessor:
    """
    Processes one camera zone in a continuous asyncio loop.

    Each FrameProcessor runs as a background task for one counter.
    Multiple processors run concurrently for multi-counter stores.
    """

    def __init__(
        self,
        zone: QueueZone,
        camera_source: str,
        camera_url: str | None,
        min_confidence: float,
        update_interval: int,
        model_path: str = "yolov8n.pt",
        device: str = "cpu",
    ) -> None:
        self.zone = zone
        self.camera_url = camera_url
        self.update_interval = update_interval
        self._zone_counter = ZoneCounter()
        self._running = False
        self._update_count = 0
        self._last_queue_length = 0

        # Determine source mode
        if camera_source == "simulation":
            self._mode = SourceMode.SIMULATION
            self._detector = None
            self._simulator = None  # Lazy init
        else:
            self._mode = SourceMode.REAL
            self._camera_url_or_index = (
                int(camera_url) if camera_url and camera_url.isdigit() else camera_url
            )
            try:
                from cv_service.detector import PersonDetector
                self._detector = PersonDetector(
                    model_path=model_path,
                    device=device,
                    min_confidence=min_confidence,
                )
            except ImportError:
                logger.warning(
                    "ultralytics not installed — falling back to simulation mode",
                    extra={"counter_id": zone.counter_id},
                )
                self._mode = SourceMode.SIMULATION
                self._detector = None

    def _get_simulator(self):
        """Lazily create the simulator (avoids import at module level)."""
        if self._simulator is None:
            from cv_service.simulator import FrameSimulator
            self._simulator = FrameSimulator(zone=self.zone)
        return self._simulator

    def _get_detections_from_real_camera(self):
        """
        Capture a frame from a real camera and run YOLOv8 detection.

        Returns list of Detection objects, or empty list on any camera error.
        """
        try:
            import cv2  # type: ignore[import]
        except ImportError:
            logger.error(
                "OpenCV (cv2) not installed. "
                "Install with: pip install opencv-python-headless"
            )
            return []

        cap = cv2.VideoCapture(self._camera_url_or_index)
        if not cap.isOpened():
            logger.error(
                "Cannot open camera",
                extra={"url": self._camera_url_or_index, "counter": self.zone.counter_id},
            )
            return []

        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            logger.warning("Empty frame captured", extra={"counter": self.zone.counter_id})
            return []

        return self._detector.detect(frame)

    async def run(self, updater) -> None:
        """
        Main processing loop for this zone.

        Runs indefinitely until stop() is called or an unrecoverable error occurs.
        Sleeps update_interval seconds between each detection cycle.

        Args:
            updater: QueueUpdater instance (shared across all processors).
        """
        self._running = True
        logger.info(
            "FrameProcessor started",
            extra={
                "counter_id": self.zone.counter_id,
                "mode": self._mode,
                "interval": self.update_interval,
            },
        )

        while self._running:
            try:
                # ── Detection ────────────────────────────────────────────────
                if self._mode == SourceMode.SIMULATION:
                    detections = self._get_simulator().generate_detections()
                else:
                    # Run synchronous OpenCV/YOLOv8 in thread pool
                    # to avoid blocking the asyncio event loop
                    loop = asyncio.get_event_loop()
                    detections = await loop.run_in_executor(
                        None, self._get_detections_from_real_camera
                    )

                # ── Zone Counting ─────────────────────────────────────────────
                queue_length = self._zone_counter.count(detections, self.zone)
                self._last_queue_length = queue_length
                self._update_count += 1

                logger.debug(
                    "Zone count",
                    extra={
                        "counter_id": self.zone.counter_id,
                        "queue_length": queue_length,
                        "total_detections": len(detections),
                        "update_count": self._update_count,
                    },
                )

                # ── Queue Engine Update ──────────────────────────────────────
                await updater.update_queue(
                    store_id=self.zone.store_id,
                    counter_id=self.zone.counter_id,
                    queue_length=queue_length,
                )

            except asyncio.CancelledError:
                logger.info(
                    "FrameProcessor cancelled",
                    extra={"counter_id": self.zone.counter_id},
                )
                break
            except Exception as exc:
                logger.error(
                    "FrameProcessor error",
                    extra={"counter_id": self.zone.counter_id, "error": str(exc)},
                    exc_info=True,
                )
                # Brief pause before retry to avoid tight error loops
                await asyncio.sleep(5)

            # ── Sleep until next cycle ────────────────────────────────────────
            await asyncio.sleep(self.update_interval)

        logger.info(
            "FrameProcessor stopped",
            extra={
                "counter_id": self.zone.counter_id,
                "total_updates": self._update_count,
            },
        )

    def stop(self) -> None:
        """Signal the processor to stop after its current cycle."""
        self._running = False

    @property
    def stats(self) -> dict:
        """Current processor statistics (for admin/health monitoring)."""
        return {
            "counter_id": self.zone.counter_id,
            "mode": self._mode,
            "last_queue_length": self._last_queue_length,
            "total_updates": self._update_count,
            "update_interval": self.update_interval,
        }
