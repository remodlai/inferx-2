"""
Pod models for function pod tracking.
"""

from pydantic import BaseModel, Field
from typing import Dict, Optional


class FuncPod(BaseModel):
    """
    Function pod object.

    Tracked by NodeAgent, queried by Scheduler/Gateway.
    """
    objType: str = Field(default="pod", description="Object type identifier")
    tenant: str = Field(description="Tenant")
    namespace: str = Field(description="Namespace")
    name: str = Field(description="Pod name/ID")

    # Pod details would go in object field
    object: Dict = Field(default_factory=dict, description="Pod specification")

    channelRev: Optional[int] = Field(default=0)
    revision: Optional[int] = Field(default=0)
    srcEpoch: Optional[int] = Field(default=0)
    labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, str] = Field(default_factory=dict)
