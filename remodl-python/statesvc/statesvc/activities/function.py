"""
Function-related activities for StateSvc.
"""

from temporalio import activity
from datetime import datetime

from inferx_common.models import Function
from .shared import get_db_connection


@activity.defn
async def create_function(function: Function) -> int:
    """Create function in PostgreSQL"""
    conn = await get_db_connection()
    try:
        await conn.execute("""
            INSERT INTO inferx.functions (tenant, namespace, name, version, spec, created_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            ON CONFLICT (tenant, namespace, name, version) DO NOTHING
        """, function.tenant, function.namespace, function.name,
            function.object.spec.version, function.object.model_dump_json())

        revision = int(datetime.now().timestamp() * 1000)
        return revision
    finally:
        await conn.close()


@activity.defn
async def update_function(function: Function) -> int:
    """Update function in PostgreSQL"""
    conn = await get_db_connection()
    try:
        await conn.execute("""
            UPDATE inferx.functions
            SET spec = $1, updated_at = NOW()
            WHERE tenant = $2 AND namespace = $3 AND name = $4 AND version = $5
        """, function.object.model_dump_json(), function.tenant, function.namespace,
            function.name, function.object.spec.version)

        revision = int(datetime.now().timestamp() * 1000)
        return revision
    finally:
        await conn.close()


@activity.defn
async def delete_function(tenant: str, namespace: str, name: str, version: int) -> int:
    """Delete function from PostgreSQL"""
    conn = await get_db_connection()
    try:
        await conn.execute("""
            DELETE FROM inferx.functions
            WHERE tenant = $1 AND namespace = $2 AND name = $3 AND version = $4
        """, tenant, namespace, name, version)

        revision = int(datetime.now().timestamp() * 1000)
        return revision
    finally:
        await conn.close()
