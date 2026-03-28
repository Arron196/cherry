from __future__ import annotations

from typing import Any

from app.services.anchor_adapter.base import (
    AnchorAdapter,
    AnchorReceiptData,
    AnchorSubmission,
    UnsupportedAdapterOperation,
)


class ReservedDualChainStubAdapter(AnchorAdapter):
    """Reserved dual-chain adapter intentionally disabled for MVP."""

    _MESSAGE = "dual-chain adapter is reserved and cannot be activated in MVP"

    def anchor_event(
        self,
        *,
        event_id: int,
        canonical_hash: str,
        payload: dict[str, Any],
    ) -> AnchorSubmission:
        raise UnsupportedAdapterOperation(self._MESSAGE)

    def get_receipt(self, transaction_hash: str) -> AnchorReceiptData:
        raise UnsupportedAdapterOperation(self._MESSAGE)

    def verify_anchor(self, *, canonical_hash: str, receipt: AnchorReceiptData | None) -> bool:
        raise UnsupportedAdapterOperation(self._MESSAGE)
