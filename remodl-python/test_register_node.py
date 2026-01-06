#!/usr/bin/env python3
"""
Test script to register gpu-workerx2 node by calling StateSvc workflow directly.
"""

import asyncio
from temporalio.client import Client
from inferx_common.models import NodeInfo, NodeSpec, NodeResources, GPUResourceMap

async def register_node():
    # Node data from etcd (matches Rust NodeSpec structure)
    node_data = {
        "nodeEpoch": 9913,
        "nodeIp": "10.42.4.12",
        "naIp": "10.42.4.8",
        "cidr": "10.0.0.0",
        "podMgrPort": 1233,
        "tsotSvcPort": 1235,
        "stateSvcPort": 1236,
        "resources": {
            "nodename": "gpu-workerx2",  # nodename is IN resources
            "CPU": 20000,
            "Mem": 92160,
            "CacheMem": 10240,
            "GPUType": "NVIDIA A100 80GB PCIe",
            "GPUs": {
                "totalSlotCnt": 279,
                "slotSize": 268435456,
                "vRam": 71424,
                "map": {
                    "0": {
                        "slotCnt": 279,
                        "contextCnt": 1,
                        "ncclCnt": 1
                    }
                }
            },
            "MaxContextPerGPU": 1
        },
        "blobStoreEnable": False,
        "CUDA_VISIBLE_DEVICES": "None",
        "state": "NodeAgentAvaiable"
    }

    # Create NodeInfo object
    node = NodeInfo(
        tenant="system",
        namespace="system",
        name="gpu-workerx2",
        object=NodeSpec(**node_data)
    )

    # Connect to Temporal
    print("Connecting to Temporal...")
    from temporalio.contrib.pydantic import pydantic_data_converter

    client = await Client.connect(
        "flow.remodl.ai:443",
        namespace="inferx",
        tls=True,
        data_converter=pydantic_data_converter
    )

    # Get workflow handle
    handle = client.get_workflow_handle("statesvc-singleton")

    # Register node via update
    print(f"Registering node: {node.name}")
    try:
        revision = await handle.execute_update(
            "register_node",
            node
        )
        print(f"✓ Node registered successfully! Revision: {revision}")
    except Exception as e:
        print(f"✗ Registration failed: {e}")
        return False

    # Verify by querying
    print("\nVerifying registration...")
    nodes = await handle.query("list_nodes")
    print(f"Total nodes in workflow: {len(nodes)}")
    for n in nodes:
        print(f"  - {n.name}: {n.object.naIp}, state={n.object.state}")

    return True

if __name__ == "__main__":
    asyncio.run(register_node())
