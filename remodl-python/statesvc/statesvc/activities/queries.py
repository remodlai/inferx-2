"""
Query activities for reading from PostgreSQL.

These are used by gRPC server to return current state.
"""

from temporalio import activity
from typing import List, Optional

from inferx_common.models import (
    Tenant, TenantObject, Namespace, NamespaceObject,
    Function, FunctionObject, FunctionStatus,
    FuncPolicy, SchedulerInfo, FuncPod, ContainerSnapshot,
    NodeInfo, NodeSpec
)
from .shared import get_db_connection


@activity.defn
async def query_tenants() -> List[Tenant]:
    """Query all tenants from PostgreSQL"""
    conn = await get_db_connection()
    try:
        rows = await conn.fetch("SELECT * FROM inferx.tenants ORDER BY name")
        return [
            Tenant(
                name=row['name'],
                object=TenantObject.model_validate_json(row['spec']),
                revision=int(row['updated_at'].timestamp() * 1000) if row['updated_at'] else 0
            )
            for row in rows
        ]
    finally:
        await conn.close()


@activity.defn
async def query_namespaces(tenant: Optional[str] = None) -> List[Namespace]:
    """Query namespaces from PostgreSQL"""
    conn = await get_db_connection()
    try:
        if tenant:
            rows = await conn.fetch("SELECT * FROM inferx.namespaces WHERE tenant = $1 ORDER BY name", tenant)
        else:
            rows = await conn.fetch("SELECT * FROM inferx.namespaces ORDER BY tenant, name")

        return [
            Namespace(
                tenant=row['tenant'],
                name=row['name'],
                object=NamespaceObject.model_validate_json(row['spec']),
                revision=int(row['updated_at'].timestamp() * 1000) if row['updated_at'] else 0
            )
            for row in rows
        ]
    finally:
        await conn.close()


@activity.defn
async def query_functions(tenant: Optional[str] = None, namespace: Optional[str] = None) -> List[Function]:
    """Query functions from PostgreSQL"""
    conn = await get_db_connection()
    try:
        if tenant and namespace:
            rows = await conn.fetch("""
                SELECT * FROM inferx.functions
                WHERE tenant = $1 AND namespace = $2
                ORDER BY name, version
            """, tenant, namespace)
        elif tenant:
            rows = await conn.fetch("""
                SELECT * FROM inferx.functions
                WHERE tenant = $1
                ORDER BY namespace, name, version
            """, tenant)
        else:
            rows = await conn.fetch("""
                SELECT * FROM inferx.functions
                ORDER BY tenant, namespace, name, version
            """)

        return [
            Function(
                tenant=row['tenant'],
                namespace=row['namespace'],
                name=row['name'],
                object=FunctionObject.model_validate_json(row['spec']),
                revision=int(row['updated_at'].timestamp() * 1000) if row['updated_at'] else 0
            )
            for row in rows
        ]
    finally:
        await conn.close()


@activity.defn
async def query_function_statuses(tenant: Optional[str] = None, namespace: Optional[str] = None) -> List[FunctionStatus]:
    """Query function statuses from PostgreSQL"""
    conn = await get_db_connection()
    try:
        if tenant and namespace:
            rows = await conn.fetch("""
                SELECT * FROM inferx.function_status
                WHERE tenant = $1 AND namespace = $2
                ORDER BY name, version
            """, tenant, namespace)
        elif tenant:
            rows = await conn.fetch("""
                SELECT * FROM inferx.function_status
                WHERE tenant = $1
                ORDER BY namespace, name, version
            """, tenant)
        else:
            rows = await conn.fetch("""
                SELECT * FROM inferx.function_status
                ORDER BY tenant, namespace, name, version
            """)

        return [
            FunctionStatus(
                tenant=row['tenant'],
                namespace=row['namespace'],
                name=row['name'],
                object={
                    "state": row['state'],
                    "version": row['version'],
                    "snapshotingFailureCnt": row['snapshoting_failure_cnt'],
                    "resumingFailureCnt": row['resuming_failure_cnt']
                },
                revision=int(row['updated_at'].timestamp() * 1000) if row['updated_at'] else 0
            )
            for row in rows
        ]
    finally:
        await conn.close()


@activity.defn
async def query_nodes() -> List[NodeInfo]:
    """Query all nodes from PostgreSQL"""
    conn = await get_db_connection()
    try:
        rows = await conn.fetch("SELECT * FROM inferx.nodes ORDER BY name")
        return [
            NodeInfo(
                name=row['name'],
                object=NodeSpec.model_validate_json(row['spec']),
                revision=int(row['updated_at'].timestamp() * 1000) if row['updated_at'] else 0
            )
            for row in rows
        ]
    finally:
        await conn.close()


# ==================== Empty Lists for Types Not Stored ====================

@activity.defn
async def query_func_policies(tenant: Optional[str] = None) -> List[FuncPolicy]:
    """Query function policies - returns empty (policies embedded in functions)"""
    return []


@activity.defn
async def query_pods(tenant: Optional[str] = None, namespace: Optional[str] = None) -> List[FuncPod]:
    """Query pods - returns empty (managed by NodeAgent)"""
    return []


@activity.defn
async def query_snapshots(tenant: Optional[str] = None) -> List[ContainerSnapshot]:
    """Query snapshots - returns empty (managed by NodeAgent)"""
    return []


@activity.defn
async def query_scheduler_info() -> Optional[SchedulerInfo]:
    """Query scheduler registration - returns None (no persistence needed)"""
    return None
