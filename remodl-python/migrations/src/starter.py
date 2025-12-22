"""
Starter script to execute migration workflow.

Usage:
    python -m src.starter
"""

import asyncio
import logging
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from dotenv import load_dotenv
import os

from .workflows import MigrationWorkflow
from .dataclasses import MigrationWorkflowInput, DatabaseConnection

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Execute migration workflow"""

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

    # Parse Neon database connection from DATABASE_URL
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://neondb_owner:npg_YIynbl1f3MUc@ep-autumn-king-a4xm63yd-pooler.us-east-1.aws.neon.tech/litellm?sslmode=require"
    )

    # Parse connection string (format: postgresql://user:pass@host:port/db?sslmode=require)
    # Simple parsing - in production use urllib.parse
    parts = database_url.replace("postgresql://", "").split("@")
    user_pass = parts[0].split(":")
    host_db = parts[1].split("/")
    host_port = host_db[0].split(":")
    db_params = host_db[1].split("?")

    db_connection = DatabaseConnection(
        host=host_port[0],
        port=int(host_port[1]) if len(host_port) > 1 else 5432,
        user=user_pass[0],
        password=user_pass[1],
        database=db_params[0],
        sslmode="require" if "sslmode=require" in database_url else "disable"
    )

    logger.info(f"Database connection: {db_connection.host}:{db_connection.port}/{db_connection.database}")

    # Create workflow input
    workflow_input = MigrationWorkflowInput(db_connection=db_connection)

    # Execute workflow
    logger.info("Starting migration workflow...")

    result = await client.execute_workflow(
        MigrationWorkflow.run,
        workflow_input,
        id="inferx-schema-migration-001",
        task_queue="migration-tasks",
    )

    # Display results
    if result.success:
        logger.info("✅ Migration completed successfully!")
        logger.info(f"   Statements executed: {result.statements_executed}")
        logger.info(f"   Validation passed: {result.validation_passed}")
        logger.info(f"   Total time: {result.total_time_ms}ms")
    else:
        logger.error("❌ Migration failed!")
        logger.error(f"   Error: {result.error_message}")
        logger.error(f"   Time: {result.total_time_ms}ms")

    return result


if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result.success else 1)
