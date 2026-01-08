"""
Common utilities for routes.
"""

import os
from temporalio.client import Client


async def get_statesvc_handle():
    """
    Create Temporal client and get StateSvcWorkflow handle.

    Returns:
        WorkflowHandle for "statesvc-workflow"
    """
    client = await Client.connect(
        os.environ["TEMPORAL_TARGET_HOST"],
        namespace=os.environ["TEMPORAL_NAMESPACE"],
        tls=True
    )
    return client.get_workflow_handle("statesvc-workflow")
