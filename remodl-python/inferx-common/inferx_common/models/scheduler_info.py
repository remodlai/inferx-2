"""
Scheduler registration model.
"""

from pydantic import BaseModel, Field
from typing import Optional


class SchedulerInfo(BaseModel):
    """
    Scheduler registration object as stored in etcd.

    Used for service discovery.
    """
    objType: str = Field(default="scheduler", description="Object type identifier")
    tenant: str = Field(default="system", description="Tenant (always 'system')")
    namespace: str = Field(default="system", description="Namespace (always 'system')")
    name: str = Field(default="scheduler", description="Name (always 'scheduler')")

    svcIp: str = Field(description="Scheduler service IP or hostname")
    port: int = Field(default=1238, description="Scheduler service port")

    channelRev: Optional[int] = Field(default=0)
    revision: Optional[int] = Field(default=0)
    srcEpoch: Optional[int] = Field(default=0)
