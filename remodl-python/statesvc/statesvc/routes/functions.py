"""
Function management routes.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from inferx_common.models import Function, FunctionStatus
from ..workflows import StateSvcWorkflow
from .common import get_statesvc_handle

router = APIRouter(prefix="/functions", tags=["functions"])


@router.get("/", response_model=dict)
async def list_functions(
    tenant: Optional[str] = Query(None),
    namespace: Optional[str] = Query(None)
):
    """List all functions with optional filters"""
    handle = await get_statesvc_handle()
    functions = await handle.query(
        StateSvcWorkflow.list_functions,
        args=[tenant, namespace]
    )
    return {"functions": functions}


@router.get("/{tenant}/{namespace}/{name}", response_model=Function)
async def get_function(
    tenant: str,
    namespace: str,
    name: str,
    version: Optional[int] = Query(None)
):
    """Get specific function (latest version if version not specified)"""
    handle = await get_statesvc_handle()
    func = await handle.query(
        StateSvcWorkflow.get_function,
        args=[tenant, namespace, name, version]
    )

    if not func:
        raise HTTPException(404, f"Function {tenant}/{namespace}/{name} not found")

    return func


@router.get("/{tenant}/{namespace}/{name}/status", response_model=FunctionStatus)
async def get_function_status(
    tenant: str,
    namespace: str,
    name: str,
    version: Optional[int] = Query(None)
):
    """Get function status"""
    handle = await get_statesvc_handle()

    # Get function to find version if not provided
    if not version:
        func = await handle.query(
            StateSvcWorkflow.get_function,
            args=[tenant, namespace, name, None]
        )
        if not func:
            raise HTTPException(404, f"Function {tenant}/{namespace}/{name} not found")
        version = func.object.spec.version

    status = await handle.query(
        StateSvcWorkflow.get_function_status,
        args=[tenant, namespace, name, version]
    )

    if not status:
        raise HTTPException(404, f"Function status not found")

    return status


@router.post("/", response_model=dict)
async def create_function(function: Function):
    """Create new function"""
    handle = await get_statesvc_handle()

    try:
        revision = await handle.execute_update(
            StateSvcWorkflow.create_function,
            args=[function]
        )
        return {
            "revision": revision,
            "status": "created",
            "function": f"{function.tenant}/{function.namespace}/{function.name}"
        }
    except Exception as e:
        raise HTTPException(400, str(e))


@router.put("/{tenant}/{namespace}/{name}", response_model=dict)
async def update_function(tenant: str, namespace: str, name: str, function: Function):
    """Update function"""
    handle = await get_statesvc_handle()

    try:
        # Merge path params into function
        function.tenant = tenant
        function.namespace = namespace
        function.name = name

        revision = await handle.execute_update(
            StateSvcWorkflow.update_function,
            args=[function]
        )
        return {"revision": revision, "status": "updated", "function": f"{tenant}/{namespace}/{name}"}
    except Exception as e:
        raise HTTPException(400, str(e))


@router.put("/{tenant}/{namespace}/{name}/status", response_model=dict)
async def update_function_status(
    tenant: str,
    namespace: str,
    name: str,
    status: FunctionStatus
):
    """Update function status"""
    handle = await get_statesvc_handle()

    try:
        # Merge path params into status
        status.tenant = tenant
        status.namespace = namespace
        status.name = name

        revision = await handle.execute_update(
            StateSvcWorkflow.update_function_status,
            args=[status]
        )
        return {"revision": revision, "status": "updated"}
    except Exception as e:
        raise HTTPException(400, str(e))


@router.delete("/{tenant}/{namespace}/{name}", response_model=dict)
async def delete_function(
    tenant: str,
    namespace: str,
    name: str,
    version: Optional[int] = Query(None)
):
    """Delete function"""
    handle = await get_statesvc_handle()

    try:
        # Get function to find version if not provided
        if not version:
            func = await handle.query(
                StateSvcWorkflow.get_function,
                args=[tenant, namespace, name, None]
            )
            if not func:
                raise HTTPException(404, f"Function {tenant}/{namespace}/{name} not found")
            version = func.object.spec.version

        revision = await handle.execute_update(
            StateSvcWorkflow.delete_function,
            args=[tenant, namespace, name, version]
        )
        return {"revision": revision, "status": "deleted", "function": f"{tenant}/{namespace}/{name}"}
    except Exception as e:
        raise HTTPException(400, str(e))
