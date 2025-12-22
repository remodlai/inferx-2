"""
GPU resource models.

Used by Node and Function specifications.
"""

from pydantic import BaseModel, Field
from typing import Dict


class GPUAlloc(BaseModel):
    """GPU allocation tracking for a single GPU device"""
    contextCnt: int = Field(description="Number of active contexts")
    slotCnt: int = Field(description="Number of VRAM slots (256MB each)")
    ncclCnt: int = Field(description="NCCL communication count")


class GPUResourceMap(BaseModel):
    """GPU resource map tracking all GPUs on a node"""
    totalSlotCnt: int = Field(description="Total VRAM slots across all GPUs")
    slotSize: int = Field(default=268435456, description="Size per slot in bytes (256MB)")
    vRam: int = Field(description="Total VRAM in MB")
    map: Dict[str, GPUAlloc] = Field(
        default_factory=dict,
        description="Per-GPU allocation map, keyed by GPU ID (0, 1, 2, ...)"
    )


class GPUResourceSpec(BaseModel):
    """GPU resource requirements for functions"""
    Type: str = Field(default="Any", description="GPU type (e.g., 'A100', 'L40', 'Any')")
    Count: int = Field(default=1, description="Number of GPUs required")
    vRam: int = Field(description="VRAM required in MB")
    contextCount: int = Field(default=0, description="Context count")
