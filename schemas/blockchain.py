from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict
from schemas.core import ORMModel

class BlockchainBlockRead(BaseModel):
    index: int
    timestamp: str
    decision_type: str
    entity_id: int
    action: str
    explanation: str
    previous_hash: str
    metadata: dict[str, Any]
    nonce: int
    hash: str | None = None


class BlockchainVerifyRead(BaseModel):
    valid: bool
    block_count: int
    tampered_indices: list[int]
    last_block_hash: str | None
