"""
Function status models.
"""

from pydantic import BaseModel, Field
from typing import Dict, Optional, Literal


class FunctionStatusDef(BaseModel):
    """Function status definition"""
    state: Literal["Normal", "Failed", "Snapshotting", "Resuming"] = Field(
        default="Normal",
        description="Function state"
    )
    version: int = Field(description="Function version")
    snapshotingFailureCnt: int = Field(default=0, description="Snapshot failure count")
    resumingFailureCnt: int = Field(default=0, description="Resume failure count")


class FunctionStatus(BaseModel):
    """Function status object as stored in etcd/database"""
    objType: str = Field(default="funcstatus", description="Object type identifier")
    tenant: str = Field(description="Tenant")
    namespace: str = Field(description="Namespace")
    name: str = Field(description="Function name")

    object: FunctionStatusDef = Field(description="Status details")

    channelRev: Optional[int] = Field(default=0)
    revision: Optional[int] = Field(default=0)
    srcEpoch: Optional[int] = Field(default=0)
    labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, str] = Field(default_factory=dict)
