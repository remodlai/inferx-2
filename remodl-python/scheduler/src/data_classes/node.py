from dataclasses import dataclass
import datetime
@dataclass


class Node:
    id: str
    name: str
    type: str
    status: str
    created_at: datetime
    updated_at: datetime