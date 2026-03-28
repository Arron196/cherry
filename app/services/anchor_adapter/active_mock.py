from __future__ import annotations

import os
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from app.services.anchor_adapter.base import (
    AnchorAdapter,
    AnchorAdapterError,
    AnchorReceiptData,
    AnchorSubmission,
    AnchorTimeoutError,
)


class ActiveMockAnchorAdapter(AnchorAdapter):
    """Deterministic active adapter used for MVP anchoring flows."""

    def __init__(self, *, mode: str | None = None, network: str | None = None) -> None:
        self._mode = mode or os.getenv("ANCHOR_MOCK_MODE", "success")
        self._network = network or os.getenv("ANCHOR_ACTIVE_NETWORK", "mvp-mock-chain")
        self._submitted_hashes: dict[str, str] = {}

    def anchor_event(
        self,
        *,
        event_id: int,
        canonical_hash: str,
        payload: dict[str, Any],
    ) -> AnchorSubmission:
        if self._mode == "timeout":
            raise AnchorTimeoutError("active mock adapter timeout")
        if self._mode == "failure":
            raise AnchorAdapterError("active mock adapter failure")
        if self._mode != "success":
            raise AnchorAdapterError(f"unsupported active mock mode: {self._mode}")

        tx_seed = f"{event_id}:{canonical_hash}".encode("utf-8")
        transaction_hash = "0x" + sha256(tx_seed).hexdigest()
        self._submitted_hashes[transaction_hash] = canonical_hash
        return AnchorSubmission(
            transaction_hash=transaction_hash,
            network=self._network,
            metadata={
                "adapter": "active_mock",
                "mode": self._mode,
                "payload_keys": sorted(payload.keys()),
            },
        )

    def get_receipt(self, transaction_hash: str) -> AnchorReceiptData:
        canonical_hash = self._submitted_hashes.get(transaction_hash)
        if canonical_hash is None:
            raise AnchorAdapterError("unknown transaction hash for active mock adapter")

        anchored_at = datetime.now(timezone.utc)
        return AnchorReceiptData(
            transaction_hash=transaction_hash,
            network=self._network,
            anchored_at=anchored_at,
            receipt_payload={
                "transaction_hash": transaction_hash,
                "network": self._network,
                "anchored_hash": canonical_hash,
                "confirmations": 1,
                "status": "finalized",
                "anchored_at": anchored_at.isoformat(),
            },
        )

    def verify_anchor(self, *, canonical_hash: str, receipt: AnchorReceiptData | None) -> bool:
        if receipt is None:
            return False
        return (
            receipt.receipt_payload.get("anchored_hash") == canonical_hash
            and receipt.receipt_payload.get("transaction_hash") == receipt.transaction_hash
        )
