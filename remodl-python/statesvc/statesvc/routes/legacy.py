"""
Legacy /object routes for backwards compatibility.

These routes proxy to modern REST API endpoints.
"""

from fastapi import APIRouter, HTTPException

from inferx_common.models import Tenant, Namespace, Function, NodeInfo, FunctionStatus
from ..workflows import StateSvcWorkflow
from .common import get_statesvc_handle

router = APIRouter(tags=["legacy"])


@router.put("/object/")
async def create_object_legacy(obj: dict):
    """
    Legacy create object endpoint.
    Routes to appropriate modern API based on 'kind' field.
    """
    kind = obj.get("kind")
    handle = await get_statesvc_handle()

    try:
        if kind == "tenant":
            tenant = Tenant(**obj)
            creator = obj.get("creator_username", "admin")
            revision = await handle.execute_update(
                StateSvcWorkflow.create_tenant,
                args=[tenant, creator]
            )
            return {"revision": revision, "status": "created"}

        elif kind == "namespace":
            namespace = Namespace(**obj)
            creator = obj.get("creator_username")
            revision = await handle.execute_update(
                StateSvcWorkflow.create_namespace,
                args=[namespace, creator]
            )
            return {"revision": revision, "status": "created"}

        elif kind == "function":
            function = Function(**obj)
            revision = await handle.execute_update(
                StateSvcWorkflow.create_function,
                args=[function]
            )
            return {"revision": revision, "status": "created"}

        elif kind == "node_info":
            node = NodeInfo(**obj)
            revision = await handle.execute_update(
                StateSvcWorkflow.register_node,
                args=[node]
            )
            return {"revision": revision, "status": "registered"}

        else:
            raise HTTPException(400, f"Unsupported object type: {kind}")

    except Exception as e:
        raise HTTPException(400, str(e))


@router.post("/object/")
async def update_object_legacy(obj: dict):
    """
    Legacy update object endpoint.
    Routes to appropriate modern API based on 'kind' field.
    """
    kind = obj.get("kind")
    handle = await get_statesvc_handle()

    try:
        if kind == "namespace":
            namespace = Namespace(**obj)
            revision = await handle.execute_update(
                StateSvcWorkflow.update_namespace,
                args=[namespace]
            )
            return {"revision": revision, "status": "updated"}

        elif kind == "function":
            function = Function(**obj)
            revision = await handle.execute_update(
                StateSvcWorkflow.update_function,
                args=[function]
            )
            return {"revision": revision, "status": "updated"}

        elif kind == "funcstatus":
            status = FunctionStatus(**obj)
            revision = await handle.execute_update(
                StateSvcWorkflow.update_function_status,
                args=[status]
            )
            return {"revision": revision, "status": "updated"}

        else:
            raise HTTPException(400, f"Unsupported object type for update: {kind}")

    except Exception as e:
        raise HTTPException(400, str(e))


@router.get("/objects/{obj_type}/{tenant}/{namespace}/")
async def list_objects_legacy(obj_type: str, tenant: str, namespace: str):
    """
    Legacy list objects endpoint.
    Routes to appropriate query based on obj_type.
    """
    handle = await get_statesvc_handle()

    try:
        if obj_type == "tenant":
            tenants = await handle.query(StateSvcWorkflow.list_tenants)
            return {"objects": tenants}

        elif obj_type == "namespace":
            # Handle empty tenant/namespace as None
            filter_tenant = None if tenant == "/" else tenant
            namespaces = await handle.query(StateSvcWorkflow.list_namespaces, args=[filter_tenant])
            return {"objects": namespaces}

        elif obj_type == "function":
            functions = await handle.query(
                StateSvcWorkflow.list_functions,
                args=[tenant if tenant != "/" else None, namespace if namespace != "/" else None]
            )
            return {"objects": functions}

        elif obj_type == "node_info":
            nodes = await handle.query(StateSvcWorkflow.list_nodes)
            return {"objects": nodes}

        elif obj_type == "funcstatus":
            statuses = await handle.query(
                StateSvcWorkflow.list_function_status,
                args=[tenant if tenant != "/" else None, namespace if namespace != "/" else None]
            )
            return {"objects": statuses}

        elif obj_type in ["funcpolicy", "pod", "snapshot", "scheduler"]:
            # Not implemented yet - return empty
            return {"objects": []}

        else:
            raise HTTPException(400, f"Unsupported object type: {obj_type}")

    except Exception as e:
        raise HTTPException(400, str(e))


@router.get("/object/{obj_type}/{tenant}/{namespace}/{name}/")
async def get_object_legacy(obj_type: str, tenant: str, namespace: str, name: str):
    """
    Legacy get object endpoint.
    Routes to appropriate query based on obj_type.
    """
    handle = await get_statesvc_handle()

    try:
        if obj_type == "tenant":
            obj = await handle.query(StateSvcWorkflow.get_tenant, args=[name])
        elif obj_type == "namespace":
            obj = await handle.query(StateSvcWorkflow.get_namespace, args=[tenant, namespace])
        elif obj_type == "function":
            obj = await handle.query(StateSvcWorkflow.get_function, args=[tenant, namespace, name, None])
        elif obj_type == "node_info":
            obj = await handle.query(StateSvcWorkflow.get_node, args=[name])
        else:
            raise HTTPException(400, f"Unsupported object type: {obj_type}")

        if not obj:
            raise HTTPException(404, f"{obj_type} not found")

        return obj

    except Exception as e:
        raise HTTPException(400, str(e))


@router.delete("/object/{obj_type}/{tenant}/{namespace}/{name}/")
async def delete_object_legacy(obj_type: str, tenant: str, namespace: str, name: str):
    """
    Legacy delete object endpoint.
    Routes to appropriate update based on obj_type.
    """
    handle = await get_statesvc_handle()

    try:
        if obj_type == "tenant":
            revision = await handle.execute_update(StateSvcWorkflow.delete_tenant, args=[name])
        elif obj_type == "namespace":
            revision = await handle.execute_update(StateSvcWorkflow.delete_namespace, args=[tenant, namespace])
        elif obj_type == "function":
            # Need to get version first
            func = await handle.query(StateSvcWorkflow.get_function, args=[tenant, namespace, name, None])
            if not func:
                raise HTTPException(404, f"Function {tenant}/{namespace}/{name} not found")
            revision = await handle.execute_update(
                StateSvcWorkflow.delete_function,
                args=[tenant, namespace, name, func.object.spec.version]
            )
        elif obj_type == "node_info":
            revision = await handle.execute_update(StateSvcWorkflow.delete_node, args=[name])
        else:
            raise HTTPException(400, f"Unsupported object type: {obj_type}")

        return {"revision": revision, "status": "deleted"}

    except Exception as e:
        raise HTTPException(400, str(e))
