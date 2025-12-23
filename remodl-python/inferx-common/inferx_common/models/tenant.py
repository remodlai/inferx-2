"""
Tenant models.
"""

from pydantic import BaseModel, Field
from typing import Dict, Optional


class TenantSpec(BaseModel):
    """Tenant specification (currently empty in production)"""
    pass


class TenantStatus(BaseModel):
    """Tenant status"""
    disable: bool = Field(default=False, description="Whether tenant is disabled")


class TenantObject(BaseModel):
    """Tenant spec and status combined"""
    spec: TenantSpec = Field(default_factory=TenantSpec)
    status: TenantStatus = Field(default_factory=TenantStatus)


class Tenant(BaseModel):
    """Tenant object as stored in etcd/database"""
    objType: str = Field(default="tenant", description="Object type identifier")
    tenant: str = Field(default="system", description="Parent tenant (always 'system')")
    namespace: str = Field(default="system", description="Parent namespace (always 'system')")
    name: str = Field(description="Tenant name (e.g., 'public')")

    object: TenantObject = Field(description="Tenant spec and status")

    channelRev: Optional[int] = Field(default=0)
    revision: Optional[int] = Field(default=0)
    srcEpoch: Optional[int] = Field(default=0)
    labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, str] = Field(default_factory=dict)
