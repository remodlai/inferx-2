"""
Worker for Nexus test workflows.

Run this in one terminal, then run test_nexus_client.py in another.
"""

import asyncio
import logging
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.contrib.pydantic import pydantic_data_converter
from dotenv import load_dotenv
import os

from .test_nexus_client import NexusTestWorkflow

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Start worker for test workflows"""

    client = await Client.connect(
        os.getenv("TEMPORAL_TARGET_HOST", "flow.remodl.ai:443"),
        namespace=os.getenv("TEMPORAL_NAMESPACE", "inferx"),
        tls=os.getenv("TEMPORAL_TLS", "true").lower() == "true",
        data_converter=pydantic_data_converter
    )

    worker = Worker(
        client,
        task_queue="nexus-test-queue",
        workflows=[NexusTestWorkflow],
    )

    logger.info("Nexus test worker started on task queue: nexus-test-queue")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
