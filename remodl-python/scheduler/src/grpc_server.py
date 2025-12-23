"""
gRPC server for Scheduler.

Implements na.proto SchedulerService, translating gRPC calls to Temporal workflow operations.
"""

import asyncio
import logging
import grpc
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from .generated import na_pb2, na_pb2_grpc
from .workflows import SchedulerWorkflow
from inferx_common.models import WorkerId

logger = logging.getLogger(__name__)


class SchedulerServiceServicer(na_pb2_grpc.SchedulerServiceServicer):
    """
    gRPC service implementation for SchedulerService.

    Translates proto requests to Temporal workflow calls.
    """

    def __init__(self, temporal_client: Client):
        self.temporal_client = temporal_client
        self.workflow_handle = temporal_client.get_workflow_handle("scheduler-singleton")

    async def ConnectScheduler(self, request, context):
        """Gateway registration"""
        try:
            # Convert proto WorkerIds to Pydantic models
            workers = [
                WorkerId(
                    tenant=w.tenant,
                    namespace=w.namespace,
                    funcname=w.funcname,
                    fprevision=w.fprevision,
                    id=w.id
                )
                for w in request.workers
            ]

            error = await self.workflow_handle.execute_update(
                SchedulerWorkflow.connect_scheduler,
                args=[request.gateway_id, workers]
            )

            return na_pb2.ConnectResp(error=error)

        except Exception as e:
            logger.error(f"ConnectScheduler error: {e}")
            return na_pb2.ConnectResp(error=str(e))

    async def LeaseWorker(self, request, context):
        """Get pod for inference request"""
        try:
            result = await self.workflow_handle.execute_update(
                SchedulerWorkflow.lease_worker,
                args=[
                    request.tenant,
                    request.namespace,
                    request.funcname,
                    request.fprevision,
                    request.gateway_id
                ]
            )

            return na_pb2.LeaseWorkerResp(
                error=result["error"],
                id=result["id"],
                ipaddr=result["ipaddr"],
                keepalive=result["keepalive"],
                hostipaddr=result.get("hostipaddr", 0),
                hostport=result.get("hostport", 0)
            )

        except Exception as e:
            logger.error(f"LeaseWorker error: {e}")
            return na_pb2.LeaseWorkerResp(
                error=str(e),
                id="",
                ipaddr=0,
                keepalive=False
            )

    async def ReturnWorker(self, request, context):
        """Release pod"""
        try:
            error = await self.workflow_handle.execute_update(
                SchedulerWorkflow.return_worker,
                args=[
                    request.tenant,
                    request.namespace,
                    request.funcname,
                    request.fprevision,
                    request.id,
                    request.failworker
                ]
            )

            return na_pb2.ReturnWorkerResp(error=error)

        except Exception as e:
            logger.error(f"ReturnWorker error: {e}")
            return na_pb2.ReturnWorkerResp(error=str(e))

    async def RefreshGateway(self, request, context):
        """Gateway heartbeat"""
        try:
            error = await self.workflow_handle.execute_update(
                SchedulerWorkflow.refresh_gateway,
                request.gateway_id
            )

            return na_pb2.RefreshGatewayResp(error=error)

        except Exception as e:
            logger.error(f"RefreshGateway error: {e}")
            return na_pb2.RefreshGatewayResp(error=str(e))

    async def serve(self, port: int = 1238):
        """Start gRPC server"""
        server = grpc.aio.server()
        na_pb2_grpc.add_SchedulerServiceServicer_to_server(self, server)
        server.add_insecure_port(f"[::]:{port}")

        logger.info(f"Starting Scheduler gRPC server on port {port}")
        await server.start()

        try:
            await server.wait_for_termination()
        except KeyboardInterrupt:
            logger.info("Shutting down Scheduler gRPC server")
            await server.stop(grace=5)


async def run_grpc_server(temporal_client: Client, port: int = 1238):
    """
    Run gRPC server for Scheduler.

    Args:
        temporal_client: Connected Temporal client
        port: Port to listen on (default 1238)
    """
    servicer = SchedulerServiceServicer(temporal_client)
    await servicer.serve(port)
