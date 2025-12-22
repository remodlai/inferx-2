"""
Namespace-related activities for StateSvc.
"""

from temporalio import activity
from datetime import datetime

from ..dataclasses import Namespace
from .shared import get_db_pool


@activity.defn
async def create_namespace(namespace: Namespace) -> int:
    """Create namespace in PostgreSQL"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO namespaces (tenant, name, spec, disabled, created_at)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (tenant, name) DO NOTHING
        """, namespace.tenant, namespace.name, namespace.object.model_dump_json(), namespace.object.status.disable)

        revision = int(datetime.now().timestamp() * 1000)
        return revision


@activity.defn
async def update_namespace(namespace: Namespace) -> int:
    """Update namespace in PostgreSQL"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE namespaces
            SET spec = $1, disabled = $2, updated_at = NOW()
            WHERE tenant = $3 AND name = $4
        """, namespace.object.model_dump_json(), namespace.object.status.disable, namespace.tenant, namespace.name)

        revision = int(datetime.now().timestamp() * 1000)
        return revision


@activity.defn
async def delete_namespace(tenant: str, namespace: str) -> int:
    """Delete namespace from PostgreSQL"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            DELETE FROM namespaces WHERE tenant = $1 AND name = $2
        """, tenant, namespace)

        revision = int(datetime.now().timestamp() * 1000)
        return revision


@activity.defn
async def grant_namespace_admin_role(tenant_name: str, namespace: str, username: str) -> None:
    """Grant namespace admin role to user"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        role_name = f"/namespace/admin/{tenant_name}/{namespace}"
        await conn.execute("""
            INSERT INTO userrole (username, rolename)
            VALUES ($1, $2)
            ON CONFLICT (username, rolename) DO NOTHING
        """, username, role_name)
