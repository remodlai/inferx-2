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
from pydantic import BaseModel
import uuid
from typing import Optional
logging.basicConfig(level=logging.INFO)



app = BoostApp(name="state-workflow-test")

class NamespaceData(BaseModel):
    inferx_namespace: str
    tenant: str
    status: str

class NamespaceResponse(BaseModel):
    inferx_namespace: str
    tenant: str
    status: str
    workflow_id: str

class NamespacesList(BaseModel):
    namespaces: list[NamespaceData]

class NamespacesResponse(BaseModel):
    namespaces: list[NamespaceResponse]

class StateData(BaseModel):
    update: dict | None = None;
    delete: dict | None = None;
    create: dict | None = None;
    
class CurrentState(BaseModel):
    version: int
    data: dict

class StateResponse(BaseModel):
    state: CurrentState
    
class StartRequest(BaseModel):
    session_id: Optional[str] = None

@workflow.defn(sandboxed=False, name="StateWorkflow")
class StateWorkflow:
    def __init__(self):
       
        self.state = {
            "version": 1,
            "data": {}
        }
    
    @workflow.run
    async def run(self) -> CurrentState:
        self.state = CurrentState(
            version=1,
            data={}
        ).model_dump(mode="json")
        
        # Keep the workflow alive, waiting for updates
        await workflow.wait_condition(lambda: False)
        
        return {
            "state": self.state,
            "workflow_id": self.workflow_id,
        }
    
    @workflow.update
    async def update_state(self, state_data: StateData) -> dict:
    # Increment version
        self.state["version"] += 1
    
    # Update: merge values into existing keys
        if state_data.update:
            for key, value in state_data.update.items():
                self.state["data"][key] = value
    
    # Delete: remove keys
        if state_data.delete:
            for key in state_data.delete:
                self.state["data"].pop(key, None)

        # Create: add only if key doesn't exist
        if state_data.create:
            for key, value in state_data.create.items():
                if key not in self.state["data"]:
                    self.state["data"][key] = value

        return self.state
    
    @workflow.query
    def get_state(self) -> dict:
        return self.state
fastapi_app = FastAPI(name="State API")    

@fastapi_app.get("/health")
async def health() -> dict:
    return {"status": "ok"}

@fastapi_app.post("/state/start")
async def start_state_workflow(request: StartRequest):
    client = await Client.connect(os.environ["TEMPORAL_TARGET_HOST"], namespace=os.environ["TEMPORAL_NAMESPACE"], tls=True)
    session_id = request.session_id or str(uuid.uuid4())
    handle = await client.start_workflow(
        StateWorkflow.run,
        id=f"state-workflow-{session_id}",  
        task_queue="state-queue",
    )
    return {"workflow_id": handle.id, "status": "started"}

@fastapi_app.post("/state/{state_id}/update")
async def update_state(state_id: str, state_data: StateData):
    client = await Client.connect(os.environ["TEMPORAL_TARGET_HOST"], namespace=os.environ["TEMPORAL_NAMESPACE"], tls=True)
    
    handle = client.get_workflow_handle(f"state-workflow-{state_id}")
    result = await handle.execute_update(
        StateWorkflow.update_state,
        state_data.model_dump(),
    )
    return result

@fastapi_app.get("/state/{state_id}")
async def get_state(state_id: str):
    client = await Client.connect(os.environ["TEMPORAL_TARGET_HOST"], namespace=os.environ["TEMPORAL_NAMESPACE"], tls=True)
    
    handle = client.get_workflow_handle(f"state-workflow-{state_id}")
    return await handle.query(StateWorkflow.get_state)

app.add_worker(
    "state-worker",
    "state-queue",
    activities=[],
    workflows=[StateWorkflow],
    
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