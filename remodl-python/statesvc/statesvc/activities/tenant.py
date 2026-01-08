"""
Tenant-related activities for StateSvc.
"""

from temporalio import activity
from datetime import datetime

from inferx_common.models import Tenant
from .shared import get_db_connection


@activity.defn
async def create_tenant_and_grant_role(tenant: Tenant, creator_username: str) -> int:
    """
    Create tenant in PostgreSQL and grant admin role to creator.

    Returns: revision number
    """
    conn = await get_db_connection()
    try:
        async with conn.transaction():
            # Insert tenant
            await conn.execute("""
                INSERT INTO inferx.tenants (name, spec, disabled, created_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (name) DO NOTHING
            """, tenant.name, tenant.object.model_dump_json(), tenant.object.status.disable)

            # Grant admin role to creator
            role_name = f"/tenant/admin/{tenant.name}"
            await conn.execute("""
                INSERT INTO inferx.userrole (username, rolename)
                VALUES ($1, $2)
                ON CONFLICT (username, rolename) DO NOTHING
            """, creator_username, role_name)

            # Return revision (timestamp-based)
            revision = int(datetime.now().timestamp() * 1000)
            return revision
    finally:
        await conn.close()


@activity.defn
async def delete_tenant(tenant_name: str) -> int:
    """Delete tenant and cascade delete associated roles"""
    conn = await get_db_connection()
    try:
        async with conn.transaction():
            # Delete tenant
            await conn.execute("DELETE FROM inferx.tenants WHERE name = $1", tenant_name)

            # Delete associated roles
            await conn.execute("""
                DELETE FROM inferx.userrole
                WHERE rolename LIKE $1
            """, f"/tenant/%/{tenant_name}%")

            revision = int(datetime.now().timestamp() * 1000)
            return revision
    finally:
        await conn.close()


@activity.defn
async def grant_tenant_admin_role(tenant_name: str, username: str) -> None:
    """Grant tenant admin role to user"""
    conn = await get_db_connection()
    try:
        role_name = f"/tenant/admin/{tenant_name}"
        await conn.execute("""
            INSERT INTO inferx.userrole (username, rolename)
            VALUES ($1, $2)
            ON CONFLICT (username, rolename) DO NOTHING
        """, username, role_name)
    finally:
        await conn.close()


@activity.defn
async def revoke_tenant_admin_role(tenant_name: str, username: str) -> None:
    """Revoke tenant admin role from user"""
    conn = await get_db_connection()
    try:
        role_name = f"/tenant/admin/{tenant_name}"
        await conn.execute("""
            DELETE FROM inferx.userrole
            WHERE username = $1 AND rolename = $2
        """, username, role_name)
    finally:
        await conn.close()
