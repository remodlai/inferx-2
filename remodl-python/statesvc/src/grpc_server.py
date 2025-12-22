"""
gRPC server for StateSvc.

Implements ixmeta.proto IxMetaService, translating gRPC calls to Temporal workflow operations.
This provides backward compatibility with IxProxy/Gateway while using Temporal backend.
"""

import asyncio
import logging
from typing import AsyncIterator
import grpc
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
import os
import json

from .generated import ixmeta_pb2, ixmeta_pb2_grpc
from .workflows import StateSvcWorkflow
from .dataclasses import (
    Tenant, TenantObject, Namespace, NamespaceObject,
    Function, FunctionObject, FunctionStatus, NodeInfo, NodeSpec
)

logger = logging.getLogger(__name__)


class IxMetaServiceServicer(ixmeta_pb2_grpc.IxMetaServiceServicer):
    """
    gRPC service implementation for IxMetaService.

    Translates proto requests to Temporal workflow calls.
    """

    def __init__(self, temporal_client: Client):
        self.temporal_client = temporal_client
        self.workflow_handle = temporal_client.get_workflow_handle("statesvc-singleton")

    async def Version(self, request, context):
        """Get StateSvc version"""
        try:
            version = await self.workflow_handle.query(StateSvcWorkflow.version)
            return ixmeta_pb2.VersionResponseMessage(version=version)
        except Exception as e:
            logger.error(f"Version error: {e}")
            return ixmeta_pb2.VersionResponseMessage(version="error")

    async def GetAddr(self, request, context):
        """Get StateSvc address"""
        try:
            addr = await self.workflow_handle.query(StateSvcWorkflow.get_addr)
            return ixmeta_pb2.GetAddrReponseMessage(
                error="",
                svc_ip=addr["svcIp"],
                port=addr["port"]
            )
        except Exception as e:
            logger.error(f"GetAddr error: {e}")
            return ixmeta_pb2.GetAddrReponseMessage(
                error=str(e),
                svc_ip="",
                port=0
            )

    async def Uid(self, request, context):
        """Get unique ID"""
        try:
            uid = await self.workflow_handle.execute_update(StateSvcWorkflow.increment_uid)
            return ixmeta_pb2.UidReponseMessage(error="", uid=uid)
        except Exception as e:
            logger.error(f"Uid error: {e}")
            return ixmeta_pb2.UidReponseMessage(error=str(e), uid=0)

    async def Create(self, request, context):
        """Create object (tenant, namespace, function, node)"""
        try:
            obj = request.obj
            obj_type = obj.kind

            # Parse object data
            data = json.loads(obj.data)

            if obj_type == "tenant":
                tenant = Tenant(
                    tenant=obj.tenant,
                    namespace=obj.namespace,
                    name=obj.name,
                    object=TenantObject(**data)
                )
                # TODO: Extract creator from auth context
                revision = await self.workflow_handle.execute_update(
                    StateSvcWorkflow.create_tenant,
                    args=[tenant, "system"]
                )

            elif obj_type == "namespace":
                namespace = Namespace(
                    tenant=obj.tenant,
                    namespace=obj.namespace,
                    name=obj.name,
                    object=NamespaceObject(**data)
                )
                revision = await self.workflow_handle.execute_update(
                    StateSvcWorkflow.create_namespace,
                    args=[namespace, None]
                )

            elif obj_type == "function":
                function = Function(
                    tenant=obj.tenant,
                    namespace=obj.namespace,
                    name=obj.name,
                    object=FunctionObject(**data)
                )
                revision = await self.workflow_handle.execute_update(
                    StateSvcWorkflow.create_function,
                    function
                )

            elif obj_type == "node_info":
                node = NodeInfo(
                    tenant=obj.tenant,
                    namespace=obj.namespace,
                    name=obj.name,
                    object=NodeSpec(**data)
                )
                revision = await self.workflow_handle.execute_update(
                    StateSvcWorkflow.register_node,
                    node
                )

            else:
                return ixmeta_pb2.CreateResponseMessage(
                    error=f"Unsupported object type: {obj_type}",
                    revision=0
                )

            return ixmeta_pb2.CreateResponseMessage(error="", revision=revision)

        except Exception as e:
            logger.error(f"Create error: {e}", exc_info=True)
            return ixmeta_pb2.CreateResponseMessage(error=str(e), revision=0)

    async def Update(self, request, context):
        """Update object"""
        try:
            obj = request.obj
            obj_type = obj.kind
            data = json.loads(obj.data)

            if obj_type == "namespace":
                namespace = Namespace(
                    tenant=obj.tenant,
                    namespace=obj.namespace,
                    name=obj.name,
                    object=NamespaceObject(**data)
                )
                revision = await self.workflow_handle.execute_update(
                    StateSvcWorkflow.update_namespace,
                    namespace
                )

            elif obj_type == "function":
                function = Function(
                    tenant=obj.tenant,
                    namespace=obj.namespace,
                    name=obj.name,
                    object=FunctionObject(**data)
                )
                revision = await self.workflow_handle.execute_update(
                    StateSvcWorkflow.update_function,
                    function
                )

            elif obj_type == "funcstatus":
                status = FunctionStatus(
                    tenant=obj.tenant,
                    namespace=obj.namespace,
                    name=obj.name,
                    object=data
                )
                revision = await self.workflow_handle.execute_update(
                    StateSvcWorkflow.update_function_status,
                    status
                )

            else:
                return ixmeta_pb2.UpdateResponseMessage(
                    error=f"Unsupported object type: {obj_type}",
                    revision=0
                )

            return ixmeta_pb2.UpdateResponseMessage(error="", revision=revision)

        except Exception as e:
            logger.error(f"Update error: {e}", exc_info=True)
            return ixmeta_pb2.UpdateResponseMessage(error=str(e), revision=0)

    async def Delete(self, request, context):
        """Delete object"""
        try:
            obj_type = request.obj_type

            if obj_type == "tenant":
                revision = await self.workflow_handle.execute_update(
                    StateSvcWorkflow.delete_tenant,
                    request.name
                )

            elif obj_type == "namespace":
                revision = await self.workflow_handle.execute_update(
                    StateSvcWorkflow.delete_namespace,
                    args=[request.tenant, request.namespace]
                )

            elif obj_type == "function":
                # Need to get version from current function
                func = await self.workflow_handle.query(
                    StateSvcWorkflow.get_function,
                    args=[request.tenant, request.namespace, request.name, None]
                )
                if not func:
                    return ixmeta_pb2.DeleteResponseMessage(
                        error=f"Function not found",
                        revision=0
                    )

                revision = await self.workflow_handle.execute_update(
                    StateSvcWorkflow.delete_function,
                    args=[request.tenant, request.namespace, request.name, func.object.spec.version]
                )

            else:
                return ixmeta_pb2.DeleteResponseMessage(
                    error=f"Unsupported object type: {obj_type}",
                    revision=0
                )

            return ixmeta_pb2.DeleteResponseMessage(error="", revision=revision)

        except Exception as e:
            logger.error(f"Delete error: {e}", exc_info=True)
            return ixmeta_pb2.DeleteResponseMessage(error=str(e), revision=0)

    async def Get(self, request, context):
        """Get object"""
        try:
            obj_type = request.obj_type

            if obj_type == "tenant":
                tenant = await self.workflow_handle.query(
                    StateSvcWorkflow.get_tenant,
                    request.name
                )
                if not tenant:
                    return ixmeta_pb2.GetResponseMessage(error="Not found", obj=None)

                # Convert to proto Obj
                obj = ixmeta_pb2.Obj(
                    kind=obj_type,
                    tenant=tenant.tenant,
                    namespace=tenant.namespace,
                    name=tenant.name,
                    revision=tenant.revision or 0,
                    data=tenant.object.model_dump_json()
                )

            elif obj_type == "namespace":
                namespace = await self.workflow_handle.query(
                    StateSvcWorkflow.get_namespace,
                    args=[request.tenant, request.namespace]
                )
                if not namespace:
                    return ixmeta_pb2.GetResponseMessage(error="Not found", obj=None)

                obj = ixmeta_pb2.Obj(
                    kind=obj_type,
                    tenant=namespace.tenant,
                    namespace=namespace.namespace,
                    name=namespace.name,
                    revision=namespace.revision or 0,
                    data=namespace.object.model_dump_json()
                )

            elif obj_type == "function":
                function = await self.workflow_handle.query(
                    StateSvcWorkflow.get_function,
                    args=[request.tenant, request.namespace, request.name, None]
                )
                if not function:
                    return ixmeta_pb2.GetResponseMessage(error="Not found", obj=None)

                obj = ixmeta_pb2.Obj(
                    kind=obj_type,
                    tenant=function.tenant,
                    namespace=function.namespace,
                    name=function.name,
                    revision=function.revision or 0,
                    data=function.object.model_dump_json()
                )

            elif obj_type == "node_info":
                node = await self.workflow_handle.query(
                    StateSvcWorkflow.get_node,
                    request.name
                )
                if not node:
                    return ixmeta_pb2.GetResponseMessage(error="Not found", obj=None)

                obj = ixmeta_pb2.Obj(
                    kind=obj_type,
                    tenant=node.tenant,
                    namespace=node.namespace,
                    name=node.name,
                    revision=node.revision or 0,
                    data=node.object.model_dump_json()
                )

            else:
                return ixmeta_pb2.GetResponseMessage(
                    error=f"Unsupported object type: {obj_type}",
                    obj=None
                )

            return ixmeta_pb2.GetResponseMessage(error="", obj=obj)

        except Exception as e:
            logger.error(f"Get error: {e}", exc_info=True)
            return ixmeta_pb2.GetResponseMessage(error=str(e), obj=None)

    async def List(self, request, context):
        """List objects"""
        try:
            obj_type = request.obj_type
            objs = []

            if obj_type == "tenant":
                tenants = await self.workflow_handle.query(StateSvcWorkflow.list_tenants)
                for tenant in tenants:
                    obj = ixmeta_pb2.Obj(
                        kind=obj_type,
                        tenant=tenant.tenant,
                        namespace=tenant.namespace,
                        name=tenant.name,
                        revision=tenant.revision or 0,
                        data=tenant.object.model_dump_json()
                    )
                    objs.append(obj)

            elif obj_type == "namespace":
                namespaces = await self.workflow_handle.query(
                    StateSvcWorkflow.list_namespaces,
                    request.tenant if request.tenant else None
                )
                for ns in namespaces:
                    obj = ixmeta_pb2.Obj(
                        kind=obj_type,
                        tenant=ns.tenant,
                        namespace=ns.namespace,
                        name=ns.name,
                        revision=ns.revision or 0,
                        data=ns.object.model_dump_json()
                    )
                    objs.append(obj)

            elif obj_type == "function":
                functions = await self.workflow_handle.query(
                    StateSvcWorkflow.list_functions,
                    args=[request.tenant if request.tenant else None,
                          request.namespace if request.namespace else None]
                )
                for func in functions:
                    obj = ixmeta_pb2.Obj(
                        kind=obj_type,
                        tenant=func.tenant,
                        namespace=func.namespace,
                        name=func.name,
                        revision=func.revision or 0,
                        data=func.object.model_dump_json()
                    )
                    objs.append(obj)

            elif obj_type == "node_info":
                nodes = await self.workflow_handle.query(StateSvcWorkflow.list_nodes)
                for node in nodes:
                    obj = ixmeta_pb2.Obj(
                        kind=obj_type,
                        tenant=node.tenant,
                        namespace=node.namespace,
                        name=node.name,
                        revision=node.revision or 0,
                        data=node.object.model_dump_json()
                    )
                    objs.append(obj)

            else:
                return ixmeta_pb2.ListResponseMessage(
                    error=f"Unsupported object type: {obj_type}",
                    revision=0,
                    objs=[]
                )

            return ixmeta_pb2.ListResponseMessage(error="", revision=0, objs=objs)

        except Exception as e:
            logger.error(f"List error: {e}", exc_info=True)
            return ixmeta_pb2.ListResponseMessage(error=str(e), revision=0, objs=[])

    async def Watch(self, request, context):
        """Watch for object changes (not implemented yet)"""
        # TODO: Implement watch using workflow signals or external state
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details("Watch not implemented in Temporal StateSvc yet")
        return

    async def serve(self, port: int = 1237):
        """Start gRPC server"""
        server = grpc.aio.server()
        ixmeta_pb2_grpc.add_IxMetaServiceServicer_to_server(self, server)
        server.add_insecure_port(f"[::]:{port}")

        logger.info(f"Starting gRPC server on port {port}")
        await server.start()

        try:
            await server.wait_for_termination()
        except KeyboardInterrupt:
            logger.info("Shutting down gRPC server")
            await server.stop(grace=5)


async def run_grpc_server(temporal_client: Client, port: int = 1237):
    """
    Run gRPC server for StateSvc.

    Args:
        temporal_client: Connected Temporal client
        port: Port to listen on (default 1237)
    """
    servicer = IxMetaServiceServicer(temporal_client)
    await servicer.serve(port)
