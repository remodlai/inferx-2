"""
Starter script to launch Scheduler singleton workflow.

Usage:
    python -m src.starter
"""

import asyncio
import logging
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from dotenv import load_dotenv
import os

from .workflows import SchedulerWorkflow

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Start the Scheduler singleton workflow"""

    temporal_address = os.getenv("TEMPORAL_TARGET_HOST", "flow.remodl.ai:443")
    temporal_namespace = os.getenv("TEMPORAL_NAMESPACE", "inferx")
    temporal_tls = os.getenv("TEMPORAL_TLS", "true").lower() == "true"

    logger.info(f"Connecting to Temporal at {temporal_address}, namespace: {temporal_namespace}")

    client = await Client.connect(
        temporal_address,
        namespace=temporal_namespace,
        tls=temporal_tls,
        data_converter=pydantic_data_converter
    )

    logger.info("Starting Scheduler singleton workflow...")

    handle = await client.start_workflow(
        SchedulerWorkflow.run,
        id="scheduler-singleton",  # Fixed ID - only one instance
        task_queue="scheduler-tasks",
    )

    logger.info(f"✅ Scheduler workflow started: {handle.id}")
    logger.info(f"   Workflow will run forever managing pod placement")

    return handle


if __name__ == "__main__":
    handle = asyncio.run(main())
    logger.info("\nScheduler is now running. Use Ctrl+C to exit (workflow continues in Temporal)")
