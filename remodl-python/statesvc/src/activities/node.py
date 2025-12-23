"""
Node-related activities for StateSvc.
"""

from temporalio import activity
from datetime import datetime

from inferx_common.models import NodeInfo
from .shared import get_db_pool


@activity.defn
async def register_node(node: NodeInfo) -> int:
    """Register or update node in PostgreSQL"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO inferx.nodes (name, node_ip, na_ip, agent_url, spec, state, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            ON CONFLICT (name)
            DO UPDATE SET node_ip = $2,
                         na_ip = $3,
                         agent_url = $4,
                         spec = $5,
                         state = $6,
                         updated_at = NOW()
        """, node.name, node.object.nodeIp, node.object.naIp,
            f"http://{node.object.naIp}:{node.object.podMgrPort}",
            node.object.model_dump_json(), node.object.state)

        revision = int(datetime.now().timestamp() * 1000)
        return revision


@activity.defn
async def update_node_state(node_name: str, state: str) -> int:
    """Update node state"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE inferx.nodes
            SET state = $1, updated_at = NOW()
            WHERE name = $2
        """, state, node_name)

        revision = int(datetime.now().timestamp() * 1000)
        return revision


@activity.defn
async def delete_node(node_name: str) -> int:
    """Delete node from PostgreSQL"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM inferx.nodes WHERE name = $1", node_name)

        revision = int(datetime.now().timestamp() * 1000)
        return revision
