"""
Routes registration for StateSvc API.
"""

from fastapi import FastAPI

from . import tenants, namespaces, functions, nodes, legacy


def register_routes(app: FastAPI):
    """
    Register all routes with FastAPI app.

    Args:
        app: FastAPI application instance
    """
    app.include_router(tenants.router)
    app.include_router(namespaces.router)
    app.include_router(functions.router)
    app.include_router(nodes.router)
    app.include_router(legacy.router)


__all__ = ["register_routes"]
