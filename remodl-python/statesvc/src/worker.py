"""
Temporal worker for StateSvc.

Registers StateSvc workflow and all activities, connects to Temporal server.
"""

import asyncio
import logging
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.contrib.pydantic import pydantic_data_converter
from dotenv import load_dotenv
import os

from .workflows import StateSvcWorkflow
from .nexus_handlers import StateSvcNexusHandler
from .activities import (
    # Tenant
    create_tenant_and_grant_role, delete_tenant,
    grant_tenant_admin_role, revoke_tenant_admin_role,
    # Namespace
    create_namespace, update_namespace, delete_namespace,
    grant_namespace_admin_role,
    # Function
    create_function, update_function, delete_function,
    # Function Status
    create_function_status, update_function_status,
    # Node
    register_node, update_node_state, delete_node,
)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Start the StateSvc worker"""

    # Temporal connection from environment
    temporal_address = os.getenv("TEMPORAL_TARGET_HOST", "flow.remodl.ai:443")
    temporal_namespace = os.getenv("TEMPORAL_NAMESPACE", "inferx")
    temporal_tls = os.getenv("TEMPORAL_TLS", "true").lower() == "true"

    logger.info(f"Connecting to Temporal at {temporal_address}, namespace: {temporal_namespace}, TLS: {temporal_tls}")

    # Connect to Temporal with Pydantic v2 data converter
    client = await Client.connect(
        temporal_address,
        namespace=temporal_namespace,
        tls=temporal_tls,
        data_converter=pydantic_data_converter
    )

    # Collect all activities
    activities = [
        # Tenant
        create_tenant_and_grant_role, delete_tenant,
        grant_tenant_admin_role, revoke_tenant_admin_role,
        # Namespace
        create_namespace, update_namespace, delete_namespace,
        grant_namespace_admin_role,
        # Function
        create_function, update_function, delete_function,
        # Function Status
        create_function_status, update_function_status,
        # Node
        register_node, update_node_state, delete_node,
    ]

    # Create worker with Nexus service handlers
    worker = Worker(
        client,
        task_queue="statesvc-tasks",
        workflows=[StateSvcWorkflow],
        activities=activities,
        nexus_service_handlers=[StateSvcNexusHandler()],
    )

    logger.info("StateSvc worker started on task queue: statesvc-tasks")
    logger.info(f"Registered workflows: StateSvcWorkflow")
    logger.info(f"Registered {len(activities)} activities")
    logger.info(f"Registered Nexus service: StateSvcNexusService")

    # Run worker (blocks until shutdown)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
