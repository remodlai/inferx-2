"""
Starter script to launch StateSvc singleton workflow.

Usage:
    python -m src.starter
"""

import asyncio
import logging
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from dotenv import load_dotenv
import os

from .workflows import StateSvcWorkflow

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Start the StateSvc singleton workflow"""

    # Temporal connection from environment
    temporal_address = os.getenv("TEMPORAL_TARGET_HOST", "flow.remodl.ai:443")
    temporal_namespace = os.getenv("TEMPORAL_NAMESPACE", "inferx")
    temporal_tls = os.getenv("TEMPORAL_TLS", "true").lower() == "true"

    logger.info(f"Connecting to Temporal at {temporal_address}, namespace: {temporal_namespace}")

    # Connect to Temporal with Pydantic v2 data converter
    client = await Client.connect(
        temporal_address,
        namespace=temporal_namespace,
        tls=temporal_tls,
        data_converter=pydantic_data_converter
    )

    # Start singleton workflow (runs forever)
    logger.info("Starting StateSvc singleton workflow...")

    handle = await client.start_workflow(
        StateSvcWorkflow.run,
        id="statesvc-singleton",  # Fixed ID - only one instance
        task_queue="statesvc-tasks",
    )

    logger.info(f"✅ StateSvc workflow started: {handle.id}")
    logger.info(f"   Workflow will run forever managing InferX state")
    logger.info(f"   Access via workflow.execute_update() and workflow.query()")

    return handle


if __name__ == "__main__":
    handle = asyncio.run(main())
    logger.info("\nStateSvc is now running. Use Ctrl+C to exit (workflow continues in Temporal)")
