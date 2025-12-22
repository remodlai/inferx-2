"""
Function-related activities for StateSvc.
"""

from temporalio import activity
from datetime import datetime

from ..dataclasses import Function
from .shared import get_db_pool


@activity.defn
async def create_function(function: Function) -> int:
    """Create function in PostgreSQL"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO functions (tenant, namespace, name, version, spec, created_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            ON CONFLICT (tenant, namespace, name, version) DO NOTHING
        """, function.tenant, function.namespace, function.name,
            function.object.spec.version, function.object.model_dump_json())

        revision = int(datetime.now().timestamp() * 1000)
        return revision


@activity.defn
async def update_function(function: Function) -> int:
    """Update function in PostgreSQL"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE functions
            SET spec = $1, updated_at = NOW()
            WHERE tenant = $2 AND namespace = $3 AND name = $4 AND version = $5
        """, function.object.model_dump_json(), function.tenant, function.namespace,
            function.name, function.object.spec.version)

        revision = int(datetime.now().timestamp() * 1000)
        return revision


@activity.defn
async def delete_function(tenant: str, namespace: str, name: str, version: int) -> int:
    """Delete function from PostgreSQL"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            DELETE FROM functions
            WHERE tenant = $1 AND namespace = $2 AND name = $3 AND version = $4
        """, tenant, namespace, name, version)

        revision = int(datetime.now().timestamp() * 1000)
        return revision
