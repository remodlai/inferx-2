"""
Function status activities for StateSvc.
"""

from temporalio import activity
from datetime import datetime

from ..dataclasses import FunctionStatus
from .shared import get_db_pool


@activity.defn
async def create_function_status(status: FunctionStatus) -> int:
    """Create function status in PostgreSQL"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO inferx.function_status (tenant, namespace, name, version, state,
                                        snapshoting_failure_cnt, resuming_failure_cnt, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            ON CONFLICT (tenant, namespace, name, version)
            DO UPDATE SET state = $5,
                         snapshoting_failure_cnt = $6,
                         resuming_failure_cnt = $7,
                         updated_at = NOW()
        """, status.tenant, status.namespace, status.name, status.object.version,
            status.object.state, status.object.snapshotingFailureCnt, status.object.resumingFailureCnt)

        revision = int(datetime.now().timestamp() * 1000)
        return revision


@activity.defn
async def update_function_status(status: FunctionStatus) -> int:
    """Update function status in PostgreSQL"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE inferx.function_status
            SET state = $1,
                snapshoting_failure_cnt = $2,
                resuming_failure_cnt = $3,
                updated_at = NOW()
            WHERE tenant = $4 AND namespace = $5 AND name = $6 AND version = $7
        """, status.object.state, status.object.snapshotingFailureCnt, status.object.resumingFailureCnt,
            status.tenant, status.namespace, status.name, status.object.version)

        revision = int(datetime.now().timestamp() * 1000)
        return revision
