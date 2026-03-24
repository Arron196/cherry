from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

SupplyChainStage = Literal["harvest", "storage", "transport", "retail"]


class SensorPayload(BaseModel):
    """Flexible sensor data envelope for canonical trace events."""

    model_config = ConfigDict(extra="allow")


class SignatureEnvelope(BaseModel):
    algorithm: str = Field(min_length=1)
    signature: str = Field(min_length=1)
    key_id: str = Field(min_length=1)


class TraceEvent(BaseModel):
    """Canonical trace event contract."""

    model_config = ConfigDict(extra="forbid")

    version: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    batch_id: str = Field(min_length=1)
    timestamp: datetime
    sensor_payload: SensorPayload
    signature_envelope: SignatureEnvelope
    co2_ppm: Optional[float] = None
    vibration_g: Optional[float] = None
    supply_chain_stage: Optional[SupplyChainStage] = None

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(*args, **kwargs)

    def canonical_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
