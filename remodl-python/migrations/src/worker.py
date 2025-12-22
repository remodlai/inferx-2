"""
Temporal worker for migration workflows.

Connects to Temporal server and registers migration workflows and activities.
"""

import asyncio
import logging
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.contrib.pydantic import pydantic_data_converter
from dotenv import load_dotenv
import os

from .workflows import MigrationWorkflow
from .activities import run_sql_migration, validate_migration

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Start the migration worker"""

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

    # Create worker
    worker = Worker(
        client,
        task_queue="migration-tasks",
        workflows=[MigrationWorkflow],
        activities=[run_sql_migration, validate_migration],
    )

    logger.info("Migration worker started on task queue: migration-tasks")
    logger.info("Registered workflows: MigrationWorkflow")
    logger.info("Registered activities: run_sql_migration, validate_migration")

    # Run worker (blocks until shutdown)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
