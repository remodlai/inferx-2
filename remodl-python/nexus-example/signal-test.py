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

logging.basicConfig(level=logging.INFO)



app = BoostApp(name="namespace-workflow-test")

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

@workflow.defn(sandboxed=False, name="NamespaceWorkflow")
class NamespaceWorkflow:
    def __init__(self):
        self.tenant = None
        self.namespaces = []
    
    @workflow.run
    async def run(self, tenant: str) -> dict:
        self.tenant = tenant
        
        # Keep the workflow alive, waiting for updates
        await workflow.wait_condition(lambda: False)
        
        return {"tenant": self.tenant, "namespaces": self.namespaces}
    
    @workflow.update
    async def add_namespace(self, namespace_data: dict) -> dict:
        self.namespaces.append(namespace_data)
        return {"status": "added", "namespace": namespace_data}
    
    @workflow.query
    def get_namespaces(self) -> list:
        return self.namespaces
fastapi_app = FastAPI(name="Namespace API")    

@fastapi_app.get("/health")
async def health() -> dict:
    return {"status": "ok"}

@fastapi_app.post("/{tenant}/namespaces/start")
async def start_namespace_workflow(tenant: str):
    client = await Client.connect(os.environ["TEMPORAL_TARGET_HOST"], namespace=os.environ["TEMPORAL_NAMESPACE"], tls=True)
    
    handle = await client.start_workflow(
        NamespaceWorkflow.run,
        tenant,
        id=f"namespace-workflow-{tenant}",  # One workflow per tenant
        task_queue="namespace-queue",
    )
    return {"workflow_id": handle.id, "status": "started"}

@fastapi_app.post("/{tenant}/namespaces/create")
async def create_namespace(tenant: str, namespace: NamespaceData):
    client = await Client.connect(os.environ["TEMPORAL_TARGET_HOST"], namespace=os.environ["TEMPORAL_NAMESPACE"], tls=True)
    
    handle = client.get_workflow_handle(f"namespace-workflow-{tenant}")
    result = await handle.execute_update(
        NamespaceWorkflow.add_namespace,
        namespace.model_dump(),
    )
    return result

@fastapi_app.get("/{tenant}/namespaces")
async def list_namespaces(tenant: str):
    client = await Client.connect(os.environ["TEMPORAL_TARGET_HOST"], namespace=os.environ["TEMPORAL_NAMESPACE"], tls=True)
    
    handle = client.get_workflow_handle(f"namespace-workflow-{tenant}")
    return await handle.query(NamespaceWorkflow.get_namespaces)

app.add_worker(
    "namespace-worker",
    "namespace-queue",
    activities=[],
    workflows=[NamespaceWorkflow],
    
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