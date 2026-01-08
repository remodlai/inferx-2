"""
StateSvc activities package.

Exports all activity functions organized by domain.
"""

from .tenant import (
    create_tenant_and_grant_role,
    delete_tenant,
    grant_tenant_admin_role,
    revoke_tenant_admin_role,
)

from .namespace import (
    create_namespace,
    update_namespace,
    delete_namespace,
    grant_namespace_admin_role,
)

from .function import (
    create_function,
    update_function,
    delete_function,
)

from .function_status import (
    create_function_status,
    update_function_status,
)

from .node import (
    register_node,
    update_node_state,
    delete_node,
)


__all__ = [
    # Tenant
    "create_tenant_and_grant_role",
    "delete_tenant",
    "grant_tenant_admin_role",
    "revoke_tenant_admin_role",
    # Namespace
    "create_namespace",
    "update_namespace",
    "delete_namespace",
    "grant_namespace_admin_role",
    # Function
    "create_function",
    "update_function",
    "delete_function",
    # Function Status
    "create_function_status",
    "update_function_status",
    # Node
    "register_node",
    "update_node_state",
    "delete_node",
]
