from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


class AnchorAdapterError(RuntimeError):
    """Base error raised by anchoring adapters."""


class AnchorTimeoutError(AnchorAdapterError):
    """Adapter indicates a transient timeout and should be retried."""


class AnchorVerificationError(AnchorAdapterError):
    """Adapter receipt exists but proof verification failed."""


class UnsupportedAdapterOperation(AnchorAdapterError):
    """Operation intentionally disabled for reserved adapters."""


@dataclass(frozen=True)
class AnchorSubmission:
    transaction_hash: str
    network: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class AnchorReceiptData:
    transaction_hash: str
    network: str
    anchored_at: datetime
    receipt_payload: dict[str, Any]


class AnchorAdapter(ABC):
    def supports_durable_submissions(self) -> bool:
        return False

    @abstractmethod
    def anchor_event(
        self,
        *,
        event_id: int,
        canonical_hash: str,
        payload: dict[str, Any],
    ) -> AnchorSubmission:
        """Submit an event hash and return transaction metadata."""

    @abstractmethod
    def get_receipt(self, transaction_hash: str) -> AnchorReceiptData:
        """Fetch finalized receipt metadata for a transaction."""

    @abstractmethod
    def verify_anchor(
        self, *, canonical_hash: str, receipt: AnchorReceiptData | None
    ) -> bool:
        """Verify that the receipt actually anchors the event hash."""
