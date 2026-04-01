from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from app.services.anchor_adapter.active_mock import ActiveMockAnchorAdapter
from app.services.anchor_adapter.base import (
    AnchorAdapter,
    AnchorAdapterError,
    AnchorTimeoutError,
    AnchorVerificationError,
    UnsupportedAdapterOperation,
)
from app.services.anchor_adapter.evm_contract import EvmContractAnchorAdapter
from app.services.anchor_adapter.reserved_stub import ReservedDualChainStubAdapter


def test_active_mock_adapter_happy_path_satisfies_contract() -> None:
    adapter = ActiveMockAnchorAdapter(mode="success", network="mvp-mock")
    assert isinstance(adapter, AnchorAdapter)

    submitted = adapter.anchor_event(
        event_id=10,
        canonical_hash="abc123",
        payload={"sensor": "stable"},
    )
    assert submitted.transaction_hash.startswith("0x")
    assert submitted.network == "mvp-mock"

    receipt = adapter.get_receipt(submitted.transaction_hash)
    assert receipt.transaction_hash == submitted.transaction_hash
    assert receipt.network == "mvp-mock"
    assert isinstance(receipt.anchored_at, datetime)
    assert receipt.anchored_at.tzinfo == timezone.utc

    assert adapter.verify_anchor(canonical_hash="abc123", receipt=receipt) is True
    assert adapter.verify_anchor(canonical_hash="different", receipt=receipt) is False


def test_active_mock_adapter_timeout_is_retryable_contract_error() -> None:
    adapter = ActiveMockAnchorAdapter(mode="timeout", network="mvp-mock")

    with pytest.raises(AnchorTimeoutError):
        adapter.anchor_event(event_id=99, canonical_hash="abc999", payload={})


def test_active_mock_adapter_failure_is_contract_error() -> None:
    adapter = ActiveMockAnchorAdapter(mode="failure", network="mvp-mock")

    with pytest.raises(AnchorAdapterError):
        adapter.anchor_event(event_id=77, canonical_hash="abc777", payload={})


def test_reserved_dual_chain_stub_is_never_active_in_mvp() -> None:
    adapter = ReservedDualChainStubAdapter()
    assert isinstance(adapter, AnchorAdapter)

    with pytest.raises(UnsupportedAdapterOperation):
        adapter.anchor_event(event_id=1, canonical_hash="hash", payload={})

    with pytest.raises(UnsupportedAdapterOperation):
        adapter.get_receipt("0x123")

    with pytest.raises(UnsupportedAdapterOperation):
        adapter.verify_anchor(canonical_hash="hash", receipt=None)


class _FakeEventFactory:
    def __init__(self, canonical_hash: bytes) -> None:
        self._canonical_hash = canonical_hash

    def __call__(self) -> _FakeEventFactory:
        return self

    def process_receipt(self, receipt: Any) -> list[dict[str, Any]]:
        del receipt
        return [{"args": {"canonicalHash": self._canonical_hash}}]


class _FakeFunctionCall:
    def __init__(self, canonical_hash: bytes, event_id: int) -> None:
        self._canonical_hash = canonical_hash
        self._event_id = event_id

    def estimate_gas(self, tx: dict[str, Any]) -> int:
        del tx
        return 90000

    def build_transaction(self, tx: dict[str, Any]) -> dict[str, Any]:
        built = dict(tx)
        built["data"] = f"0x{self._canonical_hash.hex()}:{self._event_id}"
        return built


class _FakeFunctions:
    def anchorEvent(self, canonical_hash: bytes, event_id: int) -> _FakeFunctionCall:
        return _FakeFunctionCall(canonical_hash, event_id)


class _FakeContract:
    def __init__(self, canonical_hash: bytes) -> None:
        self.functions = _FakeFunctions()
        self.events = SimpleNamespace(HashAnchored=_FakeEventFactory(canonical_hash))


class _FakeAccount:
    def from_key(self, private_key: str) -> SimpleNamespace:
        del private_key
        return SimpleNamespace(address="0xabc123")

    def sign_transaction(self, tx: dict[str, Any], private_key: str) -> SimpleNamespace:
        del tx, private_key
        return SimpleNamespace(raw_transaction=b"signed")


class _FakeEth:
    def __init__(self, canonical_hash: bytes) -> None:
        self.account = _FakeAccount()
        self.chain_id = 31337
        self.gas_price = 1_000_000_000
        self.max_priority_fee = 2_000_000_000
        self.block_number = 30
        self._canonical_hash = canonical_hash

    def contract(self, address: str, abi: list[dict[str, Any]]) -> _FakeContract:
        del address, abi
        return _FakeContract(self._canonical_hash)

    def get_transaction_count(self, address: str, block_tag: str) -> int:
        del address, block_tag
        return 8

    def send_raw_transaction(self, raw_transaction: bytes) -> bytes:
        del raw_transaction
        return bytes.fromhex("ab" * 32)

    def send_transaction(self, tx: dict[str, Any]) -> bytes:
        del tx
        return bytes.fromhex("cd" * 32)

    def wait_for_transaction_receipt(
        self,
        tx_hash: str,
        *,
        timeout: int,
        poll_latency: int,
    ) -> dict[str, Any]:
        del tx_hash, timeout, poll_latency
        return {
            "status": 1,
            "blockNumber": 22,
            "blockHash": bytes.fromhex("aa" * 32),
            "gasUsed": 88000,
            "effectiveGasPrice": 1_000_000_000,
            "transactionIndex": 1,
        }

    def get_transaction_receipt(self, tx_hash: str) -> dict[str, Any]:
        del tx_hash
        return {
            "status": 1,
            "blockNumber": 22,
            "blockHash": bytes.fromhex("aa" * 32),
            "gasUsed": 88000,
            "effectiveGasPrice": 1_000_000_000,
            "transactionIndex": 1,
        }

    def get_transaction(self, tx_hash: str) -> dict[str, Any]:
        del tx_hash
        return {"input": "0x12345678" + self._canonical_hash.hex() + ("00" * 32)}

    def get_block(self, block_number: int | str) -> dict[str, Any]:
        if block_number == "latest":
            return {
                "number": self.block_number,
                "baseFeePerGas": 1_000_000_000,
                "hash": bytes.fromhex("aa" * 32),
            }
        return {
            "timestamp": 1_700_000_000,
            "number": int(block_number),
            "hash": bytes.fromhex("aa" * 32),
        }


class _ReorgEth(_FakeEth):
    def get_transaction_receipt(self, tx_hash: str) -> dict[str, Any]:
        del tx_hash
        return {
            "status": 1,
            "blockNumber": 22,
            "blockHash": bytes.fromhex("bb" * 32),
            "gasUsed": 88000,
            "effectiveGasPrice": 1_000_000_000,
            "transactionIndex": 1,
        }


class _FakeWeb3:
    def __init__(self, canonical_hash: bytes) -> None:
        self.eth = _FakeEth(canonical_hash)

    def is_connected(self) -> bool:
        return True

    def to_checksum_address(self, value: str) -> str:
        return value


class _ReorgWeb3:
    def __init__(self, canonical_hash: bytes) -> None:
        self.eth = _ReorgEth(canonical_hash)

    def is_connected(self) -> bool:
        return True

    def to_checksum_address(self, value: str) -> str:
        return value


def test_evm_contract_adapter_happy_path_satisfies_contract() -> None:
    canonical_hash = "1" * 64
    fake_web3 = _FakeWeb3(bytes.fromhex(canonical_hash))
    adapter = EvmContractAnchorAdapter(
        web3_client=fake_web3,
        contract_address="0x1111111111111111111111111111111111111111",
        account_address="0x2222222222222222222222222222222222222222",
        network="evm-testnet",
        receipt_timeout_seconds=5,
        poll_interval_seconds=1,
    )
    assert isinstance(adapter, AnchorAdapter)
    assert adapter.supports_durable_submissions() is True

    submission = adapter.anchor_event(
        event_id=7, canonical_hash=canonical_hash, payload={}
    )
    assert submission.network == "evm-testnet"
    assert submission.transaction_hash.startswith("0x")

    receipt = adapter.get_receipt(submission.transaction_hash)
    assert receipt.network == "evm-testnet"
    assert receipt.receipt_payload["status"] == "success"
    assert receipt.anchored_at.tzinfo == timezone.utc

    assert adapter.verify_anchor(canonical_hash=canonical_hash, receipt=receipt) is True
    assert adapter.verify_anchor(canonical_hash="2" * 64, receipt=receipt) is False


def test_evm_contract_adapter_requires_account_identity() -> None:
    fake_web3 = _FakeWeb3(bytes.fromhex("3" * 64))
    with pytest.raises(AnchorAdapterError):
        EvmContractAnchorAdapter(
            web3_client=fake_web3,
            contract_address="0x3333333333333333333333333333333333333333",
            account_address=None,
            private_key=None,
        )


def test_evm_contract_adapter_supports_external_signer_without_private_key() -> None:
    canonical_hash = "4" * 64
    fake_web3 = _FakeWeb3(bytes.fromhex(canonical_hash))

    def _signer(unsigned_tx: dict[str, Any]) -> str:
        del unsigned_tx
        return "0x" + ("99" * 32)

    adapter = EvmContractAnchorAdapter(
        web3_client=fake_web3,
        contract_address="0x4444444444444444444444444444444444444444",
        account_address="0x5555555555555555555555555555555555555555",
        private_key=None,
        signer_fn=_signer,
    )

    submission = adapter.anchor_event(
        event_id=1, canonical_hash=canonical_hash, payload={}
    )
    assert submission.transaction_hash.startswith("0x")


def test_evm_contract_adapter_detects_reorg_during_confirmation_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANCHOR_EVM_REQUIRED_CONFIRMATIONS", "2")
    canonical_hash = "6" * 64
    fake_web3 = _ReorgWeb3(bytes.fromhex(canonical_hash))
    adapter = EvmContractAnchorAdapter(
        web3_client=fake_web3,
        contract_address="0x6666666666666666666666666666666666666666",
        account_address="0x7777777777777777777777777777777777777777",
        receipt_timeout_seconds=2,
        poll_interval_seconds=1,
    )

    submission = adapter.anchor_event(
        event_id=1, canonical_hash=canonical_hash, payload={}
    )
    with pytest.raises(AnchorVerificationError):
        adapter.get_receipt(submission.transaction_hash)
