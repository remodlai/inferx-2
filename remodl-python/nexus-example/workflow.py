import logging
import os
from datetime import timedelta

# Set env vars BEFORE importing temporal_boost
os.environ["TEMPORAL_TARGET_HOST"] = "flow.remodl.ai:443"
os.environ["TEMPORAL_NAMESPACE"] = "remodl"
os.environ["TEMPORAL_TLS"] = "true"

from temporalio import activity, workflow
from temporalio.client import Client
from temporal_boost import BoostApp, ASGIWorkerType
from temporal_boost.temporal import config
from fastapi import FastAPI
from dataclasses import dataclass
import uuid

logging.basicConfig(level=logging.INFO)



app = BoostApp(name="greeting-workflow-test")
fastapi_app = FastAPI(name="My API")

@fastapi_app.get("/health")
async def health() -> dict:
    return {"status": "ok"}

@dataclass
class GreetingWorkflowInput:
    name: str

@dataclass
class GreetingWorkflowOutput:
    greeting: str

@activity.defn(name="greet")
async def greet(name: str) -> str:
    greeting = f"Hello, {name}!"
    return greeting

@workflow.defn(sandboxed=False, name="GreetingWorkflow")
class GreetingWorkflow:
    

    @workflow.run
    async def run(self, input: str) -> str:
        return await workflow.execute_activity(
            greet,
            input,
            task_queue="greeting-queue",
            start_to_close_timeout=timedelta(seconds=10),
        )

@workflow.defn(sandboxed=False, name="StatusWorkflow")
class StatusWorkflow:
    def __init__(self):
        self.status = "inactive"

    @workflow.run
    async def run(self, input: str) -> str:
        return await workflow.execute_activity(
            greet,
            input,
            task_queue="status-queue",
            start_to_close_timeout=timedelta(seconds=10),
        )

    @workflow.signal(name="start")
    async def start(self):
        self.status = "active"

    @workflow.signal(name="stop")
    async def stop(self):
        self.status = "inactive"

    @workflow.query(name="status")
    async def status(self) -> dict:
        return {"status": self.status}
        
@fastapi_app.post("/greeting")
async def start_workflow(workflow_data: GreetingWorkflowInput):
    client = await Client.connect(os.environ["TEMPORAL_TARGET_HOST"], namespace=os.environ["TEMPORAL_NAMESPACE"], tls=True)
   
    greeting = await client.start_workflow(
        "GreetingWorkflow",
        workflow_data.name,
        id=f"greeting-workflow2-{uuid.uuid4()}",
        task_queue="greeting-queue",
    )
    return {"greeting": await greeting.result()}
app.add_worker(
    "greeting-worker",
    "greeting-queue",
    activities=[greet],
    workflows=[GreetingWorkflow],
    
)
app.add_asgi_worker(
    "api_worker",
    fastapi_app,
    "0.0.0.0",
    8000,
    asgi_worker_type=ASGIWorkerType.auto,
)

if __name__ == "__main__":
    app.run()