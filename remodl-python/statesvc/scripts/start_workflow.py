"""
One-time script to start StateSvcWorkflow.

Run with: python -m scripts.start_workflow (from statesvc directory)
Or: cd /Users/brianbagdasarian/projects/inferx-2/remodl-python && python statesvc/scripts/start_workflow.py
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment from parent directory
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from temporalio.client import Client
from statesvc.workflows import StateSvcWorkflow


async def start_statesvc_workflow():
    """Start the StateSvc workflow"""
    print("Connecting to Temporal...")
    print(f"  Host: {os.environ.get('TEMPORAL_TARGET_HOST')}")
    print(f"  Namespace: {os.environ.get('TEMPORAL_NAMESPACE')}")

    client = await Client.connect(
        os.environ["TEMPORAL_TARGET_HOST"],
        namespace=os.environ["TEMPORAL_NAMESPACE"],
        tls=True
    )

    print("\nStarting StateSvcWorkflow...")

    try:
        handle = await client.start_workflow(
            StateSvcWorkflow.run,
            id="statesvc-workflow",
            task_queue="statesvc-workflow-queue"
        )
        print(f"✅ Workflow started successfully!")
        print(f"   Workflow ID: {handle.id}")
        print(f"   Run ID: {handle.result_run_id}")

    except Exception as e:
        if "already started" in str(e).lower() or "already exists" in str(e).lower():
            print(f"ℹ️  Workflow 'statesvc-workflow' already running")
        else:
            print(f"❌ Error starting workflow: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(start_statesvc_workflow())
