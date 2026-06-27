"""
RetailFlow AI — Store & Counter API Router

REST endpoints for store management:

Store CRUD (Admin only):
  POST   /api/v1/stores                          → Create store
  GET    /api/v1/stores                          → List stores (paginated)
  GET    /api/v1/stores/{store_id}               → Get store details
  PATCH  /api/v1/stores/{store_id}               → Update store
  DELETE /api/v1/stores/{store_id}               → Deactivate store

Manager Assignment (Admin only):
  POST   /api/v1/stores/{store_id}/managers      → Assign manager
  GET    /api/v1/stores/{store_id}/managers      → List managers
  DELETE /api/v1/stores/{store_id}/managers/{id} → Remove manager

Counter Management (Admin + Manager):
  POST   /api/v1/stores/{store_id}/counters      → Add counter
  GET    /api/v1/stores/{store_id}/counters      → List counters
  PATCH  /api/v1/counters/{counter_id}           → Update counter
  DELETE /api/v1/counters/{counter_id}           → Soft-delete counter
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth.dependencies import AdminUser, ManagerUser, get_current_active_user
from app.core.database import get_db
from app.models.store import CounterStatus
from app.models.user import User, UserRole
from app.schemas.common import APIResponse
from app.schemas.store import (
    AssignManagerRequest,
    CounterCreateRequest,
    CounterResponse,
    CounterUpdateRequest,
    ManagerSummary,
    PaginationMeta,
    StoreCreateRequest,
    StoreDetailResponse,
    StoreListResponse,
    StoreResponse,
    StoreUpdateRequest,
)
from app.services.store_service import (
    AccessDeniedError,
    CounterNotFoundError,
    DuplicateCounterError,
    ManagerAlreadyAssignedError,
    ManagerNotFoundError,
    StoreNotFoundError,
    StoreService,
    get_store_service,
)

router = APIRouter()

# ─────────────────────────────────────────────────────────────────────────────
# Helpers: map domain exceptions → HTTP exceptions
# ─────────────────────────────────────────────────────────────────────────────

def _raise_for_store_errors(exc: Exception) -> None:
    """Central mapping of store domain exceptions to HTTP status codes."""
    if isinstance(exc, StoreNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "STORE_NOT_FOUND", "message": str(exc)},
        )
    if isinstance(exc, CounterNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "COUNTER_NOT_FOUND", "message": str(exc)},
        )
    if isinstance(exc, DuplicateCounterError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DUPLICATE_COUNTER", "message": str(exc)},
        )
    if isinstance(exc, ManagerNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "MANAGER_NOT_FOUND", "message": str(exc)},
        )
    if isinstance(exc, ManagerAlreadyAssignedError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "MANAGER_ALREADY_ASSIGNED", "message": str(exc)},
        )
    if isinstance(exc, AccessDeniedError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": str(exc)},
        )
    raise exc  # Unknown exception — re-raise for 500


# =============================================================================
# Store Endpoints
# =============================================================================

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=APIResponse[StoreResponse],
    summary="Create a new store",
    description="Admin only. Creates a new retail store owned by the authenticated admin.",
)
async def create_store(
    data: StoreCreateRequest,
    current_user: AdminUser,
    db: AsyncSession = Depends(get_db),
    store_service: StoreService = Depends(get_store_service),
) -> APIResponse[StoreResponse]:
    try:
        store = await store_service.create_store(db, data, current_user)
        total, open_count = await store_service._store_repo.get_counter_stats(db, store.id)
        return APIResponse(
            data=StoreResponse.from_store(store, total, open_count),
            message=f"Store '{store.name}' created successfully",
        )
    except Exception as e:
        _raise_for_store_errors(e)


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[StoreListResponse],
    summary="List stores",
    description=(
        "Returns a paginated list of stores. "
        "Admins see all stores; managers see only their assigned stores."
    ),
)
async def list_stores(
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(default=1, ge=1, description="Page number"),
    limit: int = Query(default=20, ge=1, le=100, description="Items per page"),
    city: str | None = Query(default=None, description="Filter by city"),
    is_active: bool | None = Query(default=None, description="Filter by active status"),
    db: AsyncSession = Depends(get_db),
    store_service: StoreService = Depends(get_store_service),
) -> APIResponse[StoreListResponse]:
    stores, total, total_pages = await store_service.list_stores(
        db, current_user, page=page, limit=limit, city=city, is_active=is_active
    )

    store_items: list[StoreResponse] = []
    for store in stores:
        total_c, open_c = await store_service._store_repo.get_counter_stats(db, store.id)
        store_items.append(StoreResponse.from_store(store, total_c, open_c))

    return APIResponse(
        data=StoreListResponse(
            items=store_items,
            meta=PaginationMeta(total=total, page=page, limit=limit, pages=total_pages),
        ),
        message=f"Retrieved {len(store_items)} stores",
    )


@router.get(
    "/{store_id}",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[StoreDetailResponse],
    summary="Get store details",
    description="Returns full store details including managers and counters.",
)
async def get_store(
    store_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
    store_service: StoreService = Depends(get_store_service),
) -> APIResponse[StoreDetailResponse]:
    try:
        store = await store_service.get_store(db, store_id, current_user)
        total_c, open_c = await store_service._store_repo.get_counter_stats(db, store.id)

        # Fetch managers and counters for detail view
        managers = await store_service._store_repo.get_store_managers(db, store_id)
        counters = await store_service._counter_repo.get_by_store(db, store_id)

        store_resp = StoreResponse.from_store(store, total_c, open_c)
        detail = StoreDetailResponse(
            **store_resp.model_dump(),
            managers=[ManagerSummary.model_validate(m) for m in managers],
            counters=[
                CounterResponse(
                    id=c.id,
                    store_id=c.store_id,
                    counter_number=c.counter_number,
                    label=c.label,
                    status=c.status,
                    cashier=None,  # Phase 5+ will populate cashier info
                    created_at=c.created_at,
                    updated_at=c.updated_at,
                )
                for c in counters
            ],
        )
        return APIResponse(data=detail, message="Store details retrieved")
    except Exception as e:
        _raise_for_store_errors(e)


@router.patch(
    "/{store_id}",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[StoreResponse],
    summary="Update store details",
    description="Partial update. Admins can update any store; managers can update their assigned stores.",
)
async def update_store(
    store_id: uuid.UUID,
    data: StoreUpdateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
    store_service: StoreService = Depends(get_store_service),
) -> APIResponse[StoreResponse]:
    try:
        store = await store_service.update_store(db, store_id, data, current_user)
        total_c, open_c = await store_service._store_repo.get_counter_stats(db, store.id)
        return APIResponse(
            data=StoreResponse.from_store(store, total_c, open_c),
            message="Store updated successfully",
        )
    except Exception as e:
        _raise_for_store_errors(e)


@router.delete(
    "/{store_id}",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[dict],
    summary="Deactivate a store",
    description="Admin only. Soft-deactivates a store (sets is_active=False).",
)
async def deactivate_store(
    store_id: uuid.UUID,
    current_user: AdminUser,
    db: AsyncSession = Depends(get_db),
    store_service: StoreService = Depends(get_store_service),
) -> APIResponse[dict]:
    try:
        data = StoreUpdateRequest(is_active=False)
        await store_service.update_store(db, store_id, data, current_user)
        return APIResponse(
            data={"store_id": str(store_id)},
            message="Store deactivated successfully",
        )
    except Exception as e:
        _raise_for_store_errors(e)


# =============================================================================
# Manager Assignment Endpoints
# =============================================================================

@router.post(
    "/{store_id}/managers",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[dict],
    summary="Assign a manager to a store",
    description="Admin only. The manager must have role='manager'.",
)
async def assign_manager(
    store_id: uuid.UUID,
    data: AssignManagerRequest,
    current_user: AdminUser,
    db: AsyncSession = Depends(get_db),
    store_service: StoreService = Depends(get_store_service),
) -> APIResponse[dict]:
    try:
        await store_service.assign_manager(db, store_id, data.manager_id)
        return APIResponse(
            data={"store_id": str(store_id), "manager_id": str(data.manager_id)},
            message="Manager assigned successfully",
        )
    except Exception as e:
        _raise_for_store_errors(e)


@router.get(
    "/{store_id}/managers",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[list[ManagerSummary]],
    summary="List managers assigned to a store",
)
async def list_managers(
    store_id: uuid.UUID,
    current_user: ManagerUser,
    db: AsyncSession = Depends(get_db),
    store_service: StoreService = Depends(get_store_service),
) -> APIResponse[list[ManagerSummary]]:
    try:
        await store_service.get_store(db, store_id, current_user)  # RBAC
        managers = await store_service._store_repo.get_store_managers(db, store_id)
        return APIResponse(
            data=[ManagerSummary.model_validate(m) for m in managers],
            message=f"Retrieved {len(managers)} managers",
        )
    except Exception as e:
        _raise_for_store_errors(e)


@router.delete(
    "/{store_id}/managers/{manager_id}",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[dict],
    summary="Remove a manager from a store",
    description="Admin only.",
)
async def remove_manager(
    store_id: uuid.UUID,
    manager_id: uuid.UUID,
    current_user: AdminUser,
    db: AsyncSession = Depends(get_db),
    store_service: StoreService = Depends(get_store_service),
) -> APIResponse[dict]:
    try:
        await store_service.remove_manager(db, store_id, manager_id)
        return APIResponse(
            data={"store_id": str(store_id), "manager_id": str(manager_id)},
            message="Manager removed from store",
        )
    except Exception as e:
        _raise_for_store_errors(e)


# =============================================================================
# Counter Endpoints
# =============================================================================

@router.post(
    "/{store_id}/counters",
    status_code=status.HTTP_201_CREATED,
    response_model=APIResponse[CounterResponse],
    summary="Add a counter to a store",
    description="Admin or assigned manager. Counter number must be unique within the store.",
)
async def create_counter(
    store_id: uuid.UUID,
    data: CounterCreateRequest,
    current_user: ManagerUser,
    db: AsyncSession = Depends(get_db),
    store_service: StoreService = Depends(get_store_service),
) -> APIResponse[CounterResponse]:
    try:
        counter = await store_service.create_counter(db, store_id, data, current_user)
        return APIResponse(
            data=CounterResponse(
                id=counter.id,
                store_id=counter.store_id,
                counter_number=counter.counter_number,
                label=counter.label,
                status=counter.status,
                cashier=None,
                created_at=counter.created_at,
                updated_at=counter.updated_at,
            ),
            message=f"Counter #{counter.counter_number} created",
        )
    except Exception as e:
        _raise_for_store_errors(e)


@router.get(
    "/{store_id}/counters",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[list[CounterResponse]],
    summary="List counters in a store",
    description="Returns all active (non-deleted) counters. Filter by status.",
)
async def list_counters(
    store_id: uuid.UUID,
    current_user: ManagerUser,
    status_filter: CounterStatus | None = Query(
        default=None, alias="status", description="Filter: open | closed | break"
    ),
    db: AsyncSession = Depends(get_db),
    store_service: StoreService = Depends(get_store_service),
) -> APIResponse[list[CounterResponse]]:
    try:
        counters = await store_service.list_counters(
            db, store_id, current_user, status=status_filter
        )
        items = [
            CounterResponse(
                id=c.id,
                store_id=c.store_id,
                counter_number=c.counter_number,
                label=c.label,
                status=c.status,
                cashier=None,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in counters
        ]
        return APIResponse(data=items, message=f"Retrieved {len(items)} counters")
    except Exception as e:
        _raise_for_store_errors(e)


@router.patch(
    "/{store_id}/counters/{counter_id}",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[CounterResponse],
    summary="Update a counter",
    description="Update label, status, or cashier assignment. Admin or assigned manager.",
)
async def update_counter(
    store_id: uuid.UUID,
    counter_id: uuid.UUID,
    data: CounterUpdateRequest,
    current_user: ManagerUser,
    db: AsyncSession = Depends(get_db),
    store_service: StoreService = Depends(get_store_service),
) -> APIResponse[CounterResponse]:
    try:
        counter = await store_service.update_counter(db, counter_id, data, current_user)
        return APIResponse(
            data=CounterResponse(
                id=counter.id,
                store_id=counter.store_id,
                counter_number=counter.counter_number,
                label=counter.label,
                status=counter.status,
                cashier=None,
                created_at=counter.created_at,
                updated_at=counter.updated_at,
            ),
            message="Counter updated successfully",
        )
    except Exception as e:
        _raise_for_store_errors(e)


@router.delete(
    "/{store_id}/counters/{counter_id}",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[dict],
    summary="Delete a counter (soft delete)",
    description=(
        "Soft-deletes the counter (preserves historical queue data). "
        "Counter is closed and cashier is unassigned. Admin or assigned manager."
    ),
)
async def delete_counter(
    store_id: uuid.UUID,
    counter_id: uuid.UUID,
    current_user: ManagerUser,
    db: AsyncSession = Depends(get_db),
    store_service: StoreService = Depends(get_store_service),
) -> APIResponse[dict]:
    try:
        await store_service.delete_counter(db, counter_id, current_user)
        return APIResponse(
            data={"counter_id": str(counter_id)},
            message="Counter removed successfully",
        )
    except Exception as e:
        _raise_for_store_errors(e)
