from dataclasses import dataclass
from typing import Any, List, Optional

import aiohttp
from temporalio import activity

from data_classes.node import Node

TASK_QUEUE_NAME = "inferx-scheduler-task-queue"

@activity.defn
async def get_node_list() -> List[Node]:
    async with aiohttp.ClientSession() as session:
        async with session.get("http://localhost:8080/api/v1/nodes") as response:
            if response.status != 200:
                raise Exception(f"Failed to get node list: {response.status}")
            nodes = await response.json()
            return [Node(**node) for node in nodes]