"""
Test StateSvc via Nexus endpoint (external call pattern).

This simulates how IxProxy/Gateway would call StateSvc operations.
"""

import asyncio
import logging
from temporalio.client import Client
from temporalio import workflow
from temporalio.contrib.pydantic import pydantic_data_converter
from dotenv import load_dotenv
import os

# Import through sandbox for workflow
with workflow.unsafe.imports_passed_through():
    from .nexus_service import StateSvcNexusService
    from inferx_common.models import (
        Tenant, TenantObject, TenantSpec, TenantStatus,
        Namespace, NamespaceObject, NamespaceSpec, NamespaceStatus,
        NodeInfo, NodeSpec, NodeResources, GPUResourceMap, GPUAlloc,
    )

# Load environment
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Simple caller workflow to test Nexus
@workflow.defn
class NexusTestWorkflow:
    """Test workflow that calls StateSvc via Nexus"""

    @workflow.run
    async def run(self) -> dict:
        """Execute Nexus operations and return results"""

        # Create Nexus client
        nexus_client = workflow.create_nexus_client(
            service=StateSvcNexusService,
            endpoint="statesvc-endpoint",
        )

        results = {}

        # Test 1: Get version (query operation)
        workflow.logger.info("Testing version query via Nexus...")
        version = await nexus_client.execute_operation(
            StateSvcNexusService.version,
            None
        )
        results["version"] = version
        workflow.logger.info(f"Version: {version}")

        # Test 2: Get address (query operation)
        workflow.logger.info("Testing get_addr query via Nexus...")
        addr = await nexus_client.execute_operation(
            StateSvcNexusService.get_addr,
            None
        )
        results["address"] = addr
        workflow.logger.info(f"Address: {addr}")

        # Test 3: List tenants (query operation)
        workflow.logger.info("Testing list_tenants query via Nexus...")
        tenants = await nexus_client.execute_operation(
            StateSvcNexusService.list_tenants,
            None
        )
        results["tenant_count"] = len(tenants)
        workflow.logger.info(f"Found {len(tenants)} tenant(s)")

        # Test 4: Create tenant (update operation)
        workflow.logger.info("Testing create_tenant update via Nexus...")
        new_tenant = Tenant(
            name="nexus-test-tenant",
            object=TenantObject(
                spec=TenantSpec(),
                status=TenantStatus(disable=False)
            )
        )

        revision = await nexus_client.execute_operation(
            StateSvcNexusService.create_tenant,
            (new_tenant, "nexus-tester")
        )
        results["tenant_revision"] = revision
        workflow.logger.info(f"Created tenant with revision: {revision}")

        # Test 5: Get the created tenant
        workflow.logger.info("Testing get_tenant query via Nexus...")
        retrieved_tenant = await nexus_client.execute_operation(
            StateSvcNexusService.get_tenant,
            "nexus-test-tenant"
        )
        results["tenant_retrieved"] = retrieved_tenant is not None
        workflow.logger.info(f"Retrieved tenant: {retrieved_tenant.name if retrieved_tenant else 'None'}")

        # Test 6: Create namespace
        workflow.logger.info("Testing create_namespace update via Nexus...")
        new_namespace = Namespace(
            tenant="nexus-test-tenant",
            name="nexus-ns",
            object=NamespaceObject(
                spec=NamespaceSpec(),
                status=NamespaceStatus(disable=False)
            )
        )

        ns_revision = await nexus_client.execute_operation(
            StateSvcNexusService.create_namespace,
            (new_namespace, "nexus-tester")
        )
        results["namespace_revision"] = ns_revision
        workflow.logger.info(f"Created namespace with revision: {ns_revision}")

        # Test 7: Register node (update operation)
        workflow.logger.info("Testing register_node update via Nexus...")
        test_node = NodeInfo(
            name="test-node-nexus",
            object=NodeSpec(
                nodename="test-node-nexus",
                nodeEpoch=1,
                nodeIp="10.42.0.100",
                naIp="10.42.0.101",
                cidr="10.0.0.0",
                podMgrPort=1233,
                stateSvcPort=1236,
                tsotSvcPort=1235,
                resources=NodeResources(
                    nodename="test-node-nexus",
                    CPU=8000,
                    Mem=32000,
                    CacheMem=5000,
                    GPUType="Test GPU",
                    GPUs=GPUResourceMap(
                        totalSlotCnt=100,
                        slotSize=268435456,
                        vRam=25600,
                        map={"0": GPUAlloc(contextCnt=1, slotCnt=100, ncclCnt=1)}
                    ),
                    MaxContextPerGPU=1
                ),
                state="NodeAgentAvaiable",
                blobStoreEnable=False,
                CUDA_VISIBLE_DEVICES="0"
            )
        )

        node_revision = await nexus_client.execute_operation(
            StateSvcNexusService.register_node,
            test_node
        )
        results["node_revision"] = node_revision
        workflow.logger.info(f"Registered node with revision: {node_revision}")

        # Test 8: Get node
        workflow.logger.info("Testing get_node query via Nexus...")
        retrieved_node = await nexus_client.execute_operation(
            StateSvcNexusService.get_node,
            "test-node-nexus"
        )
        results["node_retrieved"] = retrieved_node is not None
        workflow.logger.info(f"Retrieved node: {retrieved_node.name if retrieved_node else 'None'}")

        workflow.logger.info("✅ All Nexus operations successful!")
        return results


async def main():
    """Run Nexus test workflow"""

    # Connect to Temporal
    client = await Client.connect(
        os.getenv("TEMPORAL_TARGET_HOST", "flow.remodl.ai:443"),
        namespace=os.getenv("TEMPORAL_NAMESPACE", "inferx"),
        tls=os.getenv("TEMPORAL_TLS", "true").lower() == "true",
        data_converter=pydantic_data_converter
    )

    logger.info("Starting Nexus test workflow...\n")

    # Execute test workflow (which calls StateSvc via Nexus)
    result = await client.execute_workflow(
        NexusTestWorkflow.run,
        id=f"nexus-test-{int(asyncio.get_event_loop().time())}",
        task_queue="nexus-test-queue",
    )

    logger.info("\n✅ Nexus test completed!")
    logger.info(f"Results: {result}")


if __name__ == "__main__":
    asyncio.run(main())
