"""
StateSvc main entry point.

Temporal Boost app running:
- FastAPI server (replacing gRPC)
- Multiple Temporal workers (workflow + activity workers)
"""

import logging
import os
from dotenv import load_dotenv

# Load environment BEFORE importing temporal_boost
load_dotenv()

from temporal_boost import BoostApp, ASGIWorkerType
from fastapi import FastAPI

from .workflows import StateSvcWorkflow
from .activities.tenant import (
    create_tenant_and_grant_role,
    delete_tenant,
    grant_tenant_admin_role,
    revoke_tenant_admin_role
)
from .activities.namespace import (
    create_namespace,
    update_namespace,
    delete_namespace,
    grant_namespace_admin_role
)
from .activities.function import (
    create_function,
    update_function,
    delete_function
)
from .activities.function_status import (
    create_function_status,
    update_function_status
)
from .activities.node import (
    register_node,
    update_node_state,
    delete_node
)

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Temporal Boost app
app = BoostApp(name="statesvc")

# Create FastAPI app
fastapi_app = FastAPI(title="InferX StateSvc")

@fastapi_app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "statesvc"}

# Register routes
from .routes import register_routes
register_routes(fastapi_app)


# 1. Workflow Worker (orchestration)
app.add_worker(
    "workflow-worker",
    "statesvc-workflow-queue",
    workflows=[StateSvcWorkflow],
    activities=[]
)

# 2. Tenant Activity Worker
app.add_worker(
    "tenant-worker",
    "tenant-queue",
    workflows=[StateSvcWorkflow],
    activities=[
        create_tenant_and_grant_role,
        delete_tenant,
        grant_tenant_admin_role,
        revoke_tenant_admin_role
    ]
)

# 3. Namespace Activity Worker
app.add_worker(
    "namespace-worker",
    "namespace-queue",
    workflows=[StateSvcWorkflow],
    activities=[
        create_namespace,
        update_namespace,
        delete_namespace,
        grant_namespace_admin_role
    ]
)

# 4. Function Activity Worker
app.add_worker(
    "function-worker",
    "function-queue",
    workflows=[StateSvcWorkflow],
    activities=[
        create_function,
        update_function,
        delete_function,
        create_function_status,
        update_function_status
    ]
)

# 5. Node Activity Worker
app.add_worker(
    "node-worker",
    "node-queue",
    workflows=[StateSvcWorkflow],
    activities=[
        register_node,
        update_node_state,
        delete_node
    ]
)

# 6. FastAPI Server
app.add_asgi_worker(
    "api-worker",
    fastapi_app,
    "0.0.0.0",
    int(os.getenv("STATESVC_PORT", "1237")),
    asgi_worker_type=ASGIWorkerType.auto
)

if __name__ == "__main__":
    app.run()
