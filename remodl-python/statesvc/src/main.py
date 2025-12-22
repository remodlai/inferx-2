"""
StateSvc main entry point.

Runs both Temporal worker and gRPC server in single process.
This is what gets containerized and deployed to Kubernetes.
"""

import asyncio
import logging
import os
from dotenv import load_dotenv
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.contrib.pydantic import pydantic_data_converter

from .workflows import StateSvcWorkflow
from .grpc_server import run_grpc_server
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

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_temporal_worker(client: Client):
    """Run Temporal worker"""

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

    # Create worker
    worker = Worker(
        client,
        task_queue=os.getenv("TEMPORAL_TASK_QUEUE", "statesvc-tasks"),
        workflows=[StateSvcWorkflow],
        activities=activities,
    )

    logger.info(f"Temporal worker started on task queue: {os.getenv('TEMPORAL_TASK_QUEUE', 'statesvc-tasks')}")
    logger.info(f"Registered workflows: StateSvcWorkflow")
    logger.info(f"Registered {len(activities)} activities")

    # Run worker
    await worker.run()


async def main():
    """Main entry point - runs both Temporal worker and gRPC server"""

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

    logger.info("Temporal client connected")

    # Get gRPC port from environment
    grpc_port = int(os.getenv("STATESVC_PORT", "1237"))

    logger.info(f"Starting StateSvc with:")
    logger.info(f"  - Temporal worker on task queue: {os.getenv('TEMPORAL_TASK_QUEUE', 'statesvc-tasks')}")
    logger.info(f"  - gRPC server on port: {grpc_port}")

    # Run both Temporal worker and gRPC server concurrently
    await asyncio.gather(
        run_temporal_worker(client),
        run_grpc_server(client, grpc_port),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("StateSvc shutting down")
