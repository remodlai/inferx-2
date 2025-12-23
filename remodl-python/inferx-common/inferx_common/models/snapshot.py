"""
Snapshot models for container snapshot tracking.
"""

from pydantic import BaseModel, Field
from typing import Dict, Optional


class ContainerSnapshot(BaseModel):
    """
    Container snapshot object.

    Tracked by NodeAgent for snapshot state.
    """
    objType: str = Field(default="snapshot", description="Object type identifier")
    tenant: str = Field(description="Tenant")
    namespace: str = Field(description="Namespace")
    name: str = Field(description="Snapshot name")

    # Snapshot details would go in object field
    object: Dict = Field(default_factory=dict, description="Snapshot specification")

    channelRev: Optional[int] = Field(default=0)
    revision: Optional[int] = Field(default=0)
    srcEpoch: Optional[int] = Field(default=0)
    labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, str] = Field(default_factory=dict)
