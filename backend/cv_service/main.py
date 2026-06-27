"""
RetailFlow AI — CV Service Entry Point

Standalone asyncio service that:
  1. Fetches all active camera zones for a store from the API
  2. Spins up one FrameProcessor task per zone
  3. Runs all processors concurrently
  4. Handles SIGTERM/SIGINT gracefully (drains in-flight updates before exit)

Usage:
    python -m cv_service.main --store-id <store_uuid>

    Or with environment variables only:
        RETAILFLOW_API_URL=http://localhost:8000
        RETAILFLOW_API_TOKEN=<admin_jwt>
        python -m cv_service.main --store-id <store_uuid>

    Or in simulation mode (no camera or YOLOv8 required):
        python -m cv_service.main --store-id <store_uuid> --simulate

Architecture:
    asyncio.gather() runs all FrameProcessor tasks concurrently.
    One task per active camera zone (one zone per counter).
    All tasks share a single QueueUpdater HTTP client (connection pooling).

    On SIGTERM:
        1. Stop all FrameProcessors (self._running = False)
        2. Cancel all asyncio tasks
        3. Close QueueUpdater HTTP client
        4. Exit cleanly

Operational Note:
    In production, this service runs as a separate Kubernetes pod
    with resource requests appropriate for the number of cameras and
    whether a GPU is available.
    Typical resource profile (CPU-only, yolov8n, 4 cameras at 5s intervals):
        CPU: 2 cores, Memory: 2GB
    With GPU (4 cameras at 1s intervals):
        CPU: 2 cores, Memory: 4GB, GPU: 0.5 NVIDIA T4
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from typing import Any

import httpx

from cv_service.config import cv_config
from cv_service.processor import FrameProcessor
from cv_service.queue_updater import QueueUpdater
from cv_service.zone_counter import QueueZone

logging.basicConfig(
    level=cv_config.log_level,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("cv_service")


async def fetch_active_zones(store_id: str) -> list[dict]:
    """
    Fetch all active camera zones for a store from the RetailFlow API.

    Returns list of zone dicts (matching CameraZoneResponse schema).
    """
    url = f"{cv_config.api_base_url.rstrip('/')}/api/v1/cameras/stores/{store_id}/zones"
    headers = {"Authorization": f"Bearer {cv_config.api_token}"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()

    data = response.json()
    zones = data.get("data", [])
    logger.info(f"Fetched {len(zones)} active camera zones for store {store_id}")
    return zones


def build_zone(zone_data: dict) -> QueueZone:
    """Convert API response dict to QueueZone value object."""
    return QueueZone(
        counter_id=zone_data["counter_id"],
        store_id=zone_data["store_id"],
        x1=zone_data["zone_x1"],
        y1=zone_data["zone_y1"],
        x2=zone_data["zone_x2"],
        y2=zone_data["zone_y2"],
        frame_width=zone_data.get("frame_width", 1280),
        frame_height=zone_data.get("frame_height", 720),
    )


async def run_cv_service(store_id: str, force_simulation: bool = False) -> None:
    """
    Main asyncio coroutine for the CV service.

    Fetches zones, starts processors, and runs until cancelled.
    """
    logger.info(f"RetailFlow CV Service starting for store {store_id}")

    # Fetch zones from API
    try:
        zones_data = await fetch_active_zones(store_id)
    except httpx.HTTPError as exc:
        logger.error(f"Failed to fetch camera zones: {exc}")
        logger.error(
            "Ensure RETAILFLOW_API_URL and RETAILFLOW_API_TOKEN are set correctly."
        )
        sys.exit(1)

    if not zones_data:
        logger.warning(
            f"No active camera zones found for store {store_id}. "
            "Configure zones via POST /api/v1/cameras/stores/{id}/counters/{id}/zone"
        )
        sys.exit(0)

    # Build processors
    processors: list[FrameProcessor] = []
    for zone_data in zones_data:
        zone = build_zone(zone_data)
        source = "simulation" if force_simulation else zone_data.get("camera_source", "simulation")
        processor = FrameProcessor(
            zone=zone,
            camera_source=source,
            camera_url=zone_data.get("camera_url"),
            min_confidence=zone_data.get("min_confidence", 0.45),
            update_interval=zone_data.get("update_interval_seconds", cv_config.default_update_interval),
            model_path=cv_config.model_path,
            device=cv_config.device,
        )
        processors.append(processor)
        logger.info(
            f"Configured processor: counter={zone.counter_id[:8]}... "
            f"source={source} interval={processor.update_interval}s"
        )

    logger.info(f"Starting {len(processors)} FrameProcessor tasks...")

    # Run all processors + updater concurrently
    async with QueueUpdater() as updater:
        tasks = [
            asyncio.create_task(
                proc.run(updater),
                name=f"processor_{proc.zone.counter_id[:8]}",
            )
            for proc in processors
        ]

        # Setup graceful shutdown on SIGTERM / SIGINT
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(
                    sig,
                    lambda: [p.stop() for p in processors] or
                            [t.cancel() for t in tasks],
                )
            except NotImplementedError:
                pass  # Windows doesn't support add_signal_handler

        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except asyncio.CancelledError:
            logger.info("CV Service tasks cancelled")
        finally:
            logger.info("CV Service shutting down...")
            for proc in processors:
                proc.stop()
            for task in tasks:
                if not task.done():
                    task.cancel()

    logger.info("CV Service stopped cleanly")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="RetailFlow AI — Computer Vision Queue Detection Service"
    )
    parser.add_argument(
        "--store-id",
        required=True,
        help="UUID of the store to monitor",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        default=False,
        help="Force simulation mode (no camera or YOLOv8 required)",
    )
    args = parser.parse_args()

    asyncio.run(
        run_cv_service(
            store_id=args.store_id,
            force_simulation=args.simulate,
        )
    )


if __name__ == "__main__":
    main()
