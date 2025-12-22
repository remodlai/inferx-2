from datetime import timedelta
from typing import Any, List, Optional

from temporalio import workflow



@workflow.defn
class SchedulerWorkflow:
    @workflow.run
    async def run(self) -> None:
        pass