"""
Tenant management routes.
"""

from fastapi import APIRouter, HTTPException

from inferx_common.models import Tenant
from ..workflows import StateSvcWorkflow
from .common import get_statesvc_handle

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/", response_model=dict)
async def list_tenants():
    """List all tenants"""
    handle = await get_statesvc_handle()
    tenants = await handle.query(StateSvcWorkflow.list_tenants)
    return {"tenants": tenants}


@router.get("/{tenant}", response_model=Tenant)
async def get_tenant(tenant: str):
    """Get specific tenant"""
    handle = await get_statesvc_handle()
    tenant_obj = await handle.query(StateSvcWorkflow.get_tenant, args=[tenant])

    if not tenant_obj:
        raise HTTPException(404, f"Tenant {tenant} not found")

    return tenant_obj


@router.post("/", response_model=dict)
async def create_tenant(tenant: Tenant, creator_username: str):
    """Create new tenant"""
    handle = await get_statesvc_handle()

    try:
        revision = await handle.execute_update(
            StateSvcWorkflow.create_tenant,
            args=[tenant, creator_username]
        )
        return {"revision": revision, "status": "created", "tenant": tenant.name}
    except Exception as e:
        raise HTTPException(400, str(e))


@router.delete("/{tenant}", response_model=dict)
async def delete_tenant(tenant: str):
    """Delete tenant"""
    handle = await get_statesvc_handle()

    try:
        revision = await handle.execute_update(
            StateSvcWorkflow.delete_tenant,
            args=[tenant]
        )
        return {"revision": revision, "status": "deleted", "tenant": tenant}
    except Exception as e:
        raise HTTPException(400, str(e))
