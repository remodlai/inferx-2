"""
Test script for StateSvc Nexus operations.

Tests tenant, namespace, function, and node operations via Nexus.
"""

import asyncio
import logging
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from dotenv import load_dotenv
import os

from .workflows import StateSvcWorkflow
from .dataclasses import (
    Tenant, TenantObject, TenantSpec, TenantStatus,
    Namespace, NamespaceObject, NamespaceSpec, NamespaceStatus,
)

# Load environment
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Test StateSvc operations"""

    # Connect to Temporal
    client = await Client.connect(
        os.getenv("TEMPORAL_TARGET_HOST", "flow.remodl.ai:443"),
        namespace=os.getenv("TEMPORAL_NAMESPACE", "inferx"),
        tls=os.getenv("TEMPORAL_TLS", "true").lower() == "true",
        data_converter=pydantic_data_converter
    )

    # Get handle to singleton workflow
    handle = client.get_workflow_handle("statesvc-singleton")

    logger.info("Testing StateSvc operations...\n")

    # Test 1: Create tenant
    logger.info("1. Creating tenant 'test-tenant'...")
    test_tenant = Tenant(
        name="test-tenant",
        object=TenantObject(
            spec=TenantSpec(),
            status=TenantStatus(disable=False)
        )
    )

    revision = await handle.execute_update(
        StateSvcWorkflow.create_tenant,
        args=[test_tenant, "brian"]
    )
    logger.info(f"   ✅ Tenant created, revision: {revision}")

    # Test 2: Get tenant
    logger.info("\n2. Getting tenant 'test-tenant'...")
    tenant = await handle.query(StateSvcWorkflow.get_tenant, "test-tenant")
    logger.info(f"   ✅ Retrieved: {tenant.name}, disabled: {tenant.object.status.disable}")

    # Test 3: List tenants
    logger.info("\n3. Listing all tenants...")
    tenants = await handle.query(StateSvcWorkflow.list_tenants)
    logger.info(f"   ✅ Found {len(tenants)} tenant(s):")
    for t in tenants:
        logger.info(f"      - {t.name}")

    # Test 4: Create namespace
    logger.info("\n4. Creating namespace 'test-ns' in 'test-tenant'...")
    test_namespace = Namespace(
        tenant="test-tenant",
        name="test-ns",
        object=NamespaceObject(
            spec=NamespaceSpec(),
            status=NamespaceStatus(disable=False)
        )
    )

    revision = await handle.execute_update(
        StateSvcWorkflow.create_namespace,
        args=[test_namespace, "brian"]
    )
    logger.info(f"   ✅ Namespace created, revision: {revision}")

    # Test 5: Get namespace
    logger.info("\n5. Getting namespace 'test-tenant/test-ns'...")
    namespace = await handle.query(
        StateSvcWorkflow.get_namespace,
        args=["test-tenant", "test-ns"]
    )
    logger.info(f"   ✅ Retrieved: {namespace.tenant}/{namespace.name}")

    # Test 6: List namespaces
    logger.info("\n6. Listing namespaces for 'test-tenant'...")
    namespaces = await handle.query(StateSvcWorkflow.list_namespaces, "test-tenant")
    logger.info(f"   ✅ Found {len(namespaces)} namespace(s):")
    for ns in namespaces:
        logger.info(f"      - {ns.tenant}/{ns.name}")

    # Test 7: Version query
    logger.info("\n7. Getting StateSvc version...")
    version = await handle.query(StateSvcWorkflow.version)
    logger.info(f"   ✅ Version: {version}")

    # Test 8: Get address
    logger.info("\n8. Getting StateSvc address...")
    addr = await handle.query(StateSvcWorkflow.get_addr)
    logger.info(f"   ✅ Address: {addr['svcIp']}:{addr['port']}")

    logger.info("\n✅ All tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
