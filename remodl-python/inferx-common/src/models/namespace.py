"""
Namespace models.
"""

from pydantic import BaseModel, Field
from typing import Dict, Optional


class NamespaceSpec(BaseModel):
    """Namespace specification (currently empty in production)"""
    pass


class NamespaceStatus(BaseModel):
    """Namespace status"""
    disable: bool = Field(default=False, description="Whether namespace is disabled")


class NamespaceObject(BaseModel):
    """Namespace spec and status combined"""
    spec: NamespaceSpec = Field(default_factory=NamespaceSpec)
    status: NamespaceStatus = Field(default_factory=NamespaceStatus)


class Namespace(BaseModel):
    """Namespace object as stored in etcd/database"""
    objType: str = Field(default="namespace", description="Object type identifier")
    tenant: str = Field(description="Parent tenant (e.g., 'public')")
    namespace: str = Field(default="system", description="Parent namespace (always 'system')")
    name: str = Field(description="Namespace name (e.g., 'test')")

    object: NamespaceObject = Field(description="Namespace spec and status")

    channelRev: Optional[int] = Field(default=0)
    revision: Optional[int] = Field(default=0)
    srcEpoch: Optional[int] = Field(default=0)
    labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, str] = Field(default_factory=dict)
