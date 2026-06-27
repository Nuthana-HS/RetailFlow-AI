"""
RetailFlow AI — Camera Zone API Router

Endpoints for configuring camera zones per counter.

  POST   /api/v1/cameras/stores/{store_id}/counters/{counter_id}/zone   → Create zone
  GET    /api/v1/cameras/stores/{store_id}/counters/{counter_id}/zone   → Get zone
  PUT    /api/v1/cameras/stores/{store_id}/counters/{counter_id}/zone   → Update zone
  DELETE /api/v1/cameras/stores/{store_id}/counters/{counter_id}/zone   → Remove zone
  GET    /api/v1/cameras/stores/{store_id}/zones                        → List all store zones
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth.dependencies import ManagerUser
from app.core.database import get_db
from app.models.user import UserRole
from app.repositories.camera_repository import CameraRepository
from app.repositories.counter_repository import CounterRepository
from app.repositories.store_repository import StoreRepository
from app.schemas.camera import CameraZoneRequest, CameraZoneResponse
from app.schemas.common import APIResponse

router = APIRouter()
_camera_repo = CameraRepository()
_store_repo = StoreRepository()
_counter_repo = CounterRepository()


async def _check_store_access(
    db: AsyncSession,
    store_id: uuid.UUID,
    requesting_user,
) -> None:
    """Verify RBAC: admin sees all, manager sees only assigned stores."""
    store = await _store_repo.get_by_id(db, store_id)
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "STORE_NOT_FOUND", "message": f"Store {store_id} not found"},
        )
    if requesting_user.role == UserRole.MANAGER:
        is_assigned = await _store_repo.is_manager_of_store(
            db, requesting_user.id, store_id
        )
        if not is_assigned:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "Not assigned to this store"},
            )
    return store


@router.post(
    "/stores/{store_id}/counters/{counter_id}/zone",
    status_code=status.HTTP_201_CREATED,
    response_model=APIResponse[CameraZoneResponse],
    summary="Configure a camera zone for a counter",
    description=(
        "Defines the rectangular region of interest (ROI) the CV service "
        "should monitor for this counter's queue. "
        "Coordinates are in pixels relative to the camera frame. "
        "Use 'simulation' source for testing without hardware."
    ),
)
async def create_camera_zone(
    store_id: uuid.UUID,
    counter_id: uuid.UUID,
    data: CameraZoneRequest,
    current_user: ManagerUser,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[CameraZoneResponse]:
    """Create a camera zone for a counter."""
    await _check_store_access(db, store_id, current_user)

    # Verify counter exists
    counter = await _counter_repo.get_by_id(db, counter_id)
    if counter is None or counter.store_id != store_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "COUNTER_NOT_FOUND", "message": f"Counter {counter_id} not found"},
        )

    # One zone per counter
    existing = await _camera_repo.get_by_counter(db, counter_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "ZONE_EXISTS",
                "message": f"Counter {counter_id} already has a camera zone. Use PUT to update.",
            },
        )

    zone = await _camera_repo.create(
        db,
        counter_id=counter_id,
        store_id=store_id,
        camera_source=data.camera_source,
        camera_url=data.camera_url,
        zone_x1=data.zone_x1,
        zone_y1=data.zone_y1,
        zone_x2=data.zone_x2,
        zone_y2=data.zone_y2,
        frame_width=data.frame_width,
        frame_height=data.frame_height,
        min_confidence=data.min_confidence,
        update_interval_seconds=data.update_interval_seconds,
    )

    return APIResponse(
        data=CameraZoneResponse.model_validate(zone),
        message="Camera zone configured",
    )


@router.get(
    "/stores/{store_id}/counters/{counter_id}/zone",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[CameraZoneResponse],
    summary="Get camera zone for a counter",
)
async def get_camera_zone(
    store_id: uuid.UUID,
    counter_id: uuid.UUID,
    current_user: ManagerUser,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[CameraZoneResponse]:
    """Get the camera zone configuration for a counter."""
    await _check_store_access(db, store_id, current_user)

    zone = await _camera_repo.get_by_counter(db, counter_id)
    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ZONE_NOT_FOUND", "message": "No camera zone configured for this counter"},
        )

    return APIResponse(
        data=CameraZoneResponse.model_validate(zone),
        message="Camera zone retrieved",
    )


@router.put(
    "/stores/{store_id}/counters/{counter_id}/zone",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[CameraZoneResponse],
    summary="Update camera zone for a counter",
)
async def update_camera_zone(
    store_id: uuid.UUID,
    counter_id: uuid.UUID,
    data: CameraZoneRequest,
    current_user: ManagerUser,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[CameraZoneResponse]:
    """Update the camera zone configuration for a counter."""
    await _check_store_access(db, store_id, current_user)

    zone = await _camera_repo.get_by_counter(db, counter_id)
    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ZONE_NOT_FOUND", "message": "No camera zone configured for this counter"},
        )

    updated = await _camera_repo.update(db, zone, data.model_dump(exclude_unset=True))
    return APIResponse(
        data=CameraZoneResponse.model_validate(updated),
        message="Camera zone updated",
    )


@router.delete(
    "/stores/{store_id}/counters/{counter_id}/zone",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[None],
    summary="Remove camera zone for a counter",
)
async def delete_camera_zone(
    store_id: uuid.UUID,
    counter_id: uuid.UUID,
    current_user: ManagerUser,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[None]:
    """Remove the camera zone for a counter (counter reverts to manual updates)."""
    await _check_store_access(db, store_id, current_user)

    zone = await _camera_repo.get_by_counter(db, counter_id)
    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ZONE_NOT_FOUND", "message": "No camera zone to delete"},
        )

    await _camera_repo.delete(db, zone)
    return APIResponse(data=None, message="Camera zone removed. Counter will use manual updates.")


@router.get(
    "/stores/{store_id}/zones",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[list[CameraZoneResponse]],
    summary="List all camera zones for a store",
    description="Returns only active zones. Used by the CV service admin dashboard.",
)
async def list_camera_zones(
    store_id: uuid.UUID,
    current_user: ManagerUser,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[CameraZoneResponse]]:
    """List all active camera zones for a store."""
    await _check_store_access(db, store_id, current_user)

    zones = await _camera_repo.get_all_active_for_store(db, store_id)
    return APIResponse(
        data=[CameraZoneResponse.model_validate(z) for z in zones],
        message=f"Retrieved {len(zones)} active camera zones",
    )
