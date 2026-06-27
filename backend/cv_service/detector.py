"""
RetailFlow AI — YOLOv8 Person Detector

Wraps the Ultralytics YOLOv8 model for person detection in queue frames.

Model Choice: YOLOv8-nano (yolov8n.pt)
    - Smallest YOLOv8 variant: 3.2M parameters, 8.7 GFLOPs
    - Inference speed: ~6ms on GPU, ~80ms on CPU (640px input)
    - COCO mAP50: 37.3 — sufficient for counting people in constrained scenes
    - File size: 6.3MB — fast download, minimal memory footprint

Counting Method — Foot Centroid:
    We use the BOTTOM-CENTER of each bounding box as the person's position.
    This is more accurate than the box center because:
      1. A person standing at a counter boundary may have their body partially
         out of the zone but their feet (and thus position) inside it.
      2. It aligns with how queue management thinks about "a person at position X".

Graceful Degradation:
    If ultralytics is not installed (e.g., in a CI environment without GPU),
    the detector raises ImportError with a clear message.
    The simulator.py handles this case by generating synthetic detections.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Detection:
    """
    A single person detection from YOLOv8.

    Bounding box is in absolute pixel coordinates (not normalized).
    cx, cy = foot centroid (bottom-center of box) used for zone assignment.
    """

    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float

    @property
    def cx(self) -> float:
        """Horizontal center of the bounding box."""
        return (self.x1 + self.x2) / 2.0

    @property
    def cy(self) -> float:
        """Bottom of the bounding box — approximates foot position."""
        return self.y2

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    def __repr__(self) -> str:
        return (
            f"Detection(bbox=({self.x1:.0f},{self.y1:.0f},{self.x2:.0f},{self.y2:.0f}) "
            f"conf={self.confidence:.2f} foot=({self.cx:.0f},{self.cy:.0f}))"
        )


class PersonDetector:
    """
    Wraps YOLOv8 for person-only detection.

    The model is loaded lazily on first use to avoid blocking the event loop
    at module import time (model loading takes ~500ms).

    Usage:
        detector = PersonDetector(model_path="yolov8n.pt", device="cpu")
        detections = detector.detect(frame)  # np.ndarray (H, W, 3) BGR
    """

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        device: str = "cpu",
        min_confidence: float = 0.45,
        person_class_id: int = 0,
    ) -> None:
        self.model_path = model_path
        self.device = device
        self.min_confidence = min_confidence
        self.person_class_id = person_class_id
        self._model = None  # Lazy load

    def _load_model(self):
        """Load YOLOv8 model on first inference call."""
        try:
            from ultralytics import YOLO  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "ultralytics is not installed. "
                "Install it with: pip install ultralytics\n"
                "For CPU-only: pip install ultralytics torch torchvision --extra-index-url "
                "https://download.pytorch.org/whl/cpu"
            ) from exc

        logger.info(
            "Loading YOLOv8 model",
            extra={"model": self.model_path, "device": self.device},
        )
        self._model = YOLO(self.model_path)
        self._model.to(self.device)
        logger.info("YOLOv8 model loaded successfully")

    def detect(self, frame: np.ndarray) -> list[Detection]:
        """
        Run person detection on a single video frame.

        Args:
            frame: OpenCV BGR image as numpy array (H, W, 3), dtype=uint8.

        Returns:
            List of Detection objects for all persons found above
            the min_confidence threshold.

        Note:
            classes=[0] restricts detection to person class only,
            which is ~3x faster than full multi-class inference.
        """
        if self._model is None:
            self._load_model()

        results = self._model(
            frame,
            classes=[self.person_class_id],  # Person only — faster
            conf=self.min_confidence,
            verbose=False,
            device=self.device,
        )

        detections: list[Detection] = []
        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                confidence = float(box.conf[0])
                detections.append(
                    Detection(
                        x1=x1,
                        y1=y1,
                        x2=x2,
                        y2=y2,
                        confidence=confidence,
                    )
                )

        logger.debug(
            "Frame detected",
            extra={
                "person_count": len(detections),
                "frame_shape": frame.shape,
            },
        )
        return detections

    def __repr__(self) -> str:
        loaded = "loaded" if self._model else "not loaded"
        return f"PersonDetector(model={self.model_path}, device={self.device}, {loaded})"
