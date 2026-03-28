from __future__ import annotations

import json
import os
import importlib
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable

import httpx

from app.services.anchor_adapter.base import (
    AnchorAdapter,
    AnchorAdapterError,
    AnchorReceiptData,
    AnchorSubmission,
    AnchorTimeoutError,
    AnchorVerificationError,
)

_DEFAULT_CONTRACT_ABI: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "anchorEvent",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "canonicalHash", "type": "bytes32"},
            {"name": "eventId", "type": "uint256"},
        ],
        "outputs": [],
    },
    {
        "type": "event",
        "name": "HashAnchored",
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "canonicalHash", "type": "bytes32"},
            {"indexed": False, "name": "eventId", "type": "uint256"},
        ],
    },
]


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise AnchorAdapterError(f"missing required environment variable: {name}")
    return value


def _optional_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        parsed = int(raw_value)
    except ValueError as exc:
        raise AnchorAdapterError(f"invalid integer for {name}: {raw_value}") from exc
    if parsed <= 0:
        raise AnchorAdapterError(f"{name} must be > 0")
    return parsed


def _optional_non_negative_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        parsed = int(raw_value)
    except ValueError as exc:
        raise AnchorAdapterError(f"invalid integer for {name}: {raw_value}") from exc
    if parsed < 0:
        raise AnchorAdapterError(f"{name} must be >= 0")
    return parsed


def _optional_int_or_none_env(name: str) -> int | None:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return None
    try:
        parsed = int(raw_value)
    except ValueError as exc:
        raise AnchorAdapterError(f"invalid integer for {name}: {raw_value}") from exc
    if parsed <= 0:
        raise AnchorAdapterError(f"{name} must be > 0")
    return parsed


def _normalize_hash(canonical_hash: str) -> str:
    normalized = canonical_hash.strip().lower()
    if normalized.startswith("0x"):
        normalized = normalized[2:]
    if len(normalized) != 64:
        raise AnchorAdapterError("canonical_hash must be 32-byte hex (64 chars)")
    try:
        int(normalized, 16)
    except ValueError as exc:
        raise AnchorAdapterError("canonical_hash must be a valid hex string") from exc
    return f"0x{normalized}"


def _hash_bytes32(canonical_hash: str) -> bytes:
    normalized = _normalize_hash(canonical_hash)
    return bytes.fromhex(normalized[2:])


def _to_utc_datetime(timestamp: int | float) -> datetime:
    return datetime.fromtimestamp(float(timestamp), tz=UTC)


@dataclass(frozen=True)
class _TxContext:
    event_id: int
    canonical_hash: str


class EvmContractAnchorAdapter(AnchorAdapter):
    def supports_durable_submissions(self) -> bool:
        return True

    def __init__(
        self,
        *,
        rpc_url: str | None = None,
        contract_address: str | None = None,
        contract_abi_json: str | None = None,
        function_name: str | None = None,
        event_name: str | None = None,
        network: str | None = None,
        chain_id: int | None = None,
        account_address: str | None = None,
        private_key: str | None = None,
        gas_limit: int | None = None,
        gas_price_wei: int | None = None,
        receipt_timeout_seconds: int | None = None,
        poll_interval_seconds: int | None = None,
        web3_client: Any | None = None,
        now_fn: Callable[[], datetime] | None = None,
        signer_fn: Callable[[dict[str, Any]], str | bytes] | None = None,
    ) -> None:
        self._now_fn = now_fn or (lambda: datetime.now(UTC))
        self._signer_fn = signer_fn

        self._rpc_url = (rpc_url or os.getenv("ANCHOR_EVM_RPC_URL", "")).strip()
        if not self._rpc_url and web3_client is None:
            raise AnchorAdapterError(
                "missing required environment variable: ANCHOR_EVM_RPC_URL"
            )

        self._network = (
            network or os.getenv("ANCHOR_EVM_NETWORK", "evm-mainnet")
        ).strip()
        self._function_name = (
            function_name or os.getenv("ANCHOR_EVM_FUNCTION_NAME", "anchorEvent")
        ).strip()
        self._event_name = (
            event_name or os.getenv("ANCHOR_EVM_EVENT_NAME", "HashAnchored")
        ).strip()

        self._receipt_timeout_seconds = (
            receipt_timeout_seconds
            if receipt_timeout_seconds is not None
            else _optional_int_env("ANCHOR_EVM_RECEIPT_TIMEOUT_SECONDS", 60)
        )
        self._poll_interval_seconds = (
            poll_interval_seconds
            if poll_interval_seconds is not None
            else _optional_int_env("ANCHOR_EVM_POLL_INTERVAL_SECONDS", 2)
        )
        self._gas_limit = (
            gas_limit
            if gas_limit is not None
            else _optional_int_env("ANCHOR_EVM_GAS_LIMIT", 250000)
        )
        self._required_confirmations = _optional_int_env(
            "ANCHOR_EVM_REQUIRED_CONFIRMATIONS", 1
        )
        self._max_submission_attempts = _optional_int_env(
            "ANCHOR_EVM_MAX_SUBMISSION_ATTEMPTS", 3
        )
        self._fee_bump_percent = _optional_non_negative_int_env(
            "ANCHOR_EVM_FEE_BUMP_PERCENT", 15
        )

        gas_price_raw = os.getenv("ANCHOR_EVM_GAS_PRICE_WEI", "").strip()
        if gas_price_wei is not None:
            self._gas_price_wei: int | None = gas_price_wei
        elif gas_price_raw:
            try:
                self._gas_price_wei = int(gas_price_raw)
            except ValueError as exc:
                raise AnchorAdapterError(
                    f"invalid integer for ANCHOR_EVM_GAS_PRICE_WEI: {gas_price_raw}"
                ) from exc
        else:
            self._gas_price_wei = None

        self._max_fee_per_gas_wei = _optional_int_or_none_env(
            "ANCHOR_EVM_MAX_FEE_PER_GAS_WEI"
        )
        self._max_priority_fee_per_gas_wei = _optional_int_or_none_env(
            "ANCHOR_EVM_MAX_PRIORITY_FEE_PER_GAS_WEI"
        )
        self._signer_url = os.getenv("ANCHOR_EVM_SIGNER_URL", "").strip() or None
        self._signer_token = os.getenv("ANCHOR_EVM_SIGNER_TOKEN", "").strip() or None
        self._signer_timeout_seconds = _optional_int_env(
            "ANCHOR_EVM_SIGNER_TIMEOUT_SECONDS", 10
        )

        if web3_client is None:
            try:
                web3_module = importlib.import_module("web3")
            except Exception as exc:
                raise AnchorAdapterError(
                    "web3 dependency missing; install web3 to use ANCHOR_ADAPTER=evm_contract"
                ) from exc
            web3_class = getattr(web3_module, "Web3", None)
            if web3_class is None:
                raise AnchorAdapterError("web3 module does not expose Web3")
            self._web3 = web3_class(web3_class.HTTPProvider(self._rpc_url))
        else:
            self._web3 = web3_client

        if not bool(getattr(self._web3, "is_connected")()):
            raise AnchorAdapterError(f"failed to connect to EVM RPC: {self._rpc_url}")

        self._chain_id = chain_id
        if self._chain_id is None:
            raw_chain_id = os.getenv("ANCHOR_EVM_CHAIN_ID", "").strip()
            if raw_chain_id:
                try:
                    self._chain_id = int(raw_chain_id)
                except ValueError as exc:
                    raise AnchorAdapterError(
                        f"invalid integer for ANCHOR_EVM_CHAIN_ID: {raw_chain_id}"
                    ) from exc

        raw_abi = (
            contract_abi_json or os.getenv("ANCHOR_EVM_CONTRACT_ABI_JSON", "")
        ).strip()
        if raw_abi:
            try:
                contract_abi = json.loads(raw_abi)
            except json.JSONDecodeError as exc:
                raise AnchorAdapterError(
                    "ANCHOR_EVM_CONTRACT_ABI_JSON must be valid JSON"
                ) from exc
        else:
            contract_abi = _DEFAULT_CONTRACT_ABI
        if not isinstance(contract_abi, list):
            raise AnchorAdapterError("contract ABI must be a JSON array")
        self._contract_abi: list[dict[str, Any]] = [
            item for item in contract_abi if isinstance(item, dict)
        ]

        configured_contract = contract_address or os.getenv(
            "ANCHOR_EVM_CONTRACT_ADDRESS", ""
        )
        if not configured_contract.strip():
            configured_contract = _required_env("ANCHOR_EVM_CONTRACT_ADDRESS")
        self._contract_address = self._to_checksum_address(configured_contract)

        self._private_key = (
            private_key or os.getenv("ANCHOR_EVM_PRIVATE_KEY", "")
        ).strip() or None
        configured_account = (
            account_address or os.getenv("ANCHOR_EVM_ACCOUNT_ADDRESS", "")
        ).strip() or None
        if configured_account is not None:
            self._account_address = self._to_checksum_address(configured_account)
        elif self._private_key is not None:
            try:
                derived = self._web3.eth.account.from_key(self._private_key).address
            except Exception as exc:
                raise AnchorAdapterError(
                    "failed to derive ANCHOR_EVM_ACCOUNT_ADDRESS from private key"
                ) from exc
            self._account_address = self._to_checksum_address(derived)
        else:
            raise AnchorAdapterError(
                "configure account identity via ANCHOR_EVM_ACCOUNT_ADDRESS or ANCHOR_EVM_PRIVATE_KEY"
            )

        self._contract = self._web3.eth.contract(
            address=self._contract_address, abi=self._contract_abi
        )
        self._function_abi = self._resolve_function_abi(self._function_name)
        self._submitted: dict[str, _TxContext] = {}

    def _to_checksum_address(self, value: str) -> str:
        converter = getattr(self._web3, "to_checksum_address", None)
        if callable(converter):
            return str(converter(value))
        raise AnchorAdapterError("web3 client does not support to_checksum_address")

    def _resolve_function_abi(self, function_name: str) -> dict[str, Any]:
        for item in self._contract_abi:
            if item.get("type") == "function" and item.get("name") == function_name:
                return item
        raise AnchorAdapterError(
            f"function '{function_name}' not found in contract ABI"
        )

    def _latest_block_number(self) -> int:
        try:
            return int(self._web3.eth.block_number)
        except Exception:
            latest_block = self._web3.eth.get_block("latest")
            if isinstance(latest_block, dict):
                return int(latest_block.get("number", 0))
            return int(getattr(latest_block, "number", 0))

    def _get_optional_network_fee_defaults(self) -> tuple[int | None, int | None]:
        priority_fee = self._max_priority_fee_per_gas_wei
        if priority_fee is None:
            try:
                priority_fee = int(self._web3.eth.max_priority_fee)
            except Exception:
                priority_fee = None

        max_fee = self._max_fee_per_gas_wei
        if max_fee is None and priority_fee is not None:
            try:
                latest = self._web3.eth.get_block("latest")
                if isinstance(latest, dict):
                    base_fee_raw = latest.get("baseFeePerGas")
                else:
                    base_fee_raw = getattr(latest, "baseFeePerGas", None)
                if base_fee_raw is not None:
                    base_fee = int(base_fee_raw)
                    max_fee = (base_fee * 2) + priority_fee
            except Exception:
                max_fee = None
        return max_fee, priority_fee

    def _build_fee_candidates(self, attempt: int) -> list[dict[str, int]]:
        multiplier = 1.0 + (self._fee_bump_percent / 100.0 * attempt)

        def _bump(value: int | None) -> int | None:
            if value is None:
                return None
            return max(1, int(value * multiplier))

        candidates: list[dict[str, int]] = []
        max_fee, priority_fee = self._get_optional_network_fee_defaults()
        bumped_max_fee = _bump(max_fee)
        bumped_priority = _bump(priority_fee)
        if bumped_max_fee is not None and bumped_priority is not None:
            if bumped_max_fee < bumped_priority:
                bumped_max_fee = bumped_priority
            candidates.append(
                {
                    "maxFeePerGas": bumped_max_fee,
                    "maxPriorityFeePerGas": bumped_priority,
                }
            )

        gas_price = _bump(self._gas_price_wei)
        if gas_price is None:
            try:
                gas_price = _bump(int(self._web3.eth.gas_price))
            except Exception:
                gas_price = None
        if gas_price is not None:
            candidates.append({"gasPrice": gas_price})

        if not candidates:
            candidates.append({})
        return candidates

    def _raw_transaction_bytes(self, value: str | bytes) -> bytes:
        if isinstance(value, bytes):
            return value
        raw = value.strip()
        if raw.startswith("0x"):
            raw = raw[2:]
        if not raw:
            raise AnchorAdapterError("external signer returned empty raw transaction")
        try:
            return bytes.fromhex(raw)
        except ValueError as exc:
            raise AnchorAdapterError(
                "external signer returned invalid hex raw transaction"
            ) from exc

    def _sign_transaction(self, unsigned_tx: dict[str, Any]) -> bytes | None:
        if self._signer_fn is not None:
            return self._raw_transaction_bytes(self._signer_fn(unsigned_tx))

        if self._signer_url is not None:
            headers: dict[str, str] = {}
            if self._signer_token:
                headers["Authorization"] = f"Bearer {self._signer_token}"
            try:
                response = httpx.post(
                    self._signer_url,
                    json={
                        "transaction": unsigned_tx,
                        "network": self._network,
                        "account_address": self._account_address,
                    },
                    headers=headers,
                    timeout=self._signer_timeout_seconds,
                )
                response.raise_for_status()
            except Exception as exc:
                raise AnchorAdapterError("failed to request external signer") from exc

            body = response.json() if response.content else {}
            if not isinstance(body, dict):
                raise AnchorAdapterError("external signer returned invalid JSON body")
            raw_tx = body.get("raw_transaction") or body.get("signed_transaction")
            if not isinstance(raw_tx, (str, bytes)):
                raise AnchorAdapterError(
                    "external signer response missing raw_transaction"
                )
            return self._raw_transaction_bytes(raw_tx)

        if self._private_key is None:
            return None
        signed = self._web3.eth.account.sign_transaction(
            unsigned_tx, private_key=self._private_key
        )
        return bytes(signed.raw_transaction)

    def _submit_with_fee_fallback(self, fn_call: Any, tx_base: dict[str, Any]) -> str:
        last_error: Exception | None = None
        for attempt in range(self._max_submission_attempts):
            for fee_overrides in self._build_fee_candidates(attempt):
                tx_payload = dict(tx_base)
                tx_payload.update(fee_overrides)
                try:
                    unsigned_tx = fn_call.build_transaction(tx_payload)
                    raw_tx = self._sign_transaction(unsigned_tx)
                    if raw_tx is not None:
                        return self._to_hex(self._web3.eth.send_raw_transaction(raw_tx))
                    return self._to_hex(self._web3.eth.send_transaction(unsigned_tx))
                except Exception as exc:
                    last_error = exc
                    continue
        raise AnchorAdapterError(
            "failed to submit transaction to EVM network"
        ) from last_error

    def _normalize_block_hash(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value if value.startswith("0x") else f"0x{value}"
        if isinstance(value, (bytes, bytearray)):
            return f"0x{bytes(value).hex()}"
        if hasattr(value, "hex") and callable(value.hex):
            rendered = value.hex()
            if isinstance(rendered, str):
                return rendered if rendered.startswith("0x") else f"0x{rendered}"
        return None

    def _get_transaction_receipt(self, tx_hash: str) -> Any | None:
        getter = getattr(self._web3.eth, "get_transaction_receipt", None)
        if not callable(getter):
            return None
        try:
            return getter(tx_hash)
        except Exception:
            return None

    def _wait_for_confirmations(self, tx_hash: str, receipt: Any) -> Any:
        block_number_raw = self._receipt_field(receipt, "blockNumber")
        block_number = int(block_number_raw) if block_number_raw is not None else 0
        if block_number <= 0 or self._required_confirmations <= 1:
            return receipt

        initial_block_hash = self._normalize_block_hash(
            self._receipt_field(receipt, "blockHash")
        )
        deadline = time.monotonic() + self._receipt_timeout_seconds
        latest_receipt = receipt

        while True:
            latest_block_number = self._latest_block_number()
            confirmations = max(0, latest_block_number - block_number + 1)
            if confirmations >= self._required_confirmations:
                break
            if time.monotonic() >= deadline:
                raise AnchorTimeoutError(
                    f"timed out waiting for {self._required_confirmations} confirmations: {tx_hash}"
                )
            time.sleep(self._poll_interval_seconds)
            refreshed = self._get_transaction_receipt(tx_hash)
            if refreshed is not None:
                latest_receipt = refreshed
                refreshed_block_raw = self._receipt_field(refreshed, "blockNumber")
                refreshed_block = (
                    int(refreshed_block_raw) if refreshed_block_raw is not None else 0
                )
                if refreshed_block != block_number:
                    raise AnchorVerificationError(
                        "reorg detected: transaction moved to different block"
                    )

        refreshed_after_confirmations = self._get_transaction_receipt(tx_hash)
        if refreshed_after_confirmations is not None:
            latest_receipt = refreshed_after_confirmations
            refreshed_block_raw = self._receipt_field(
                refreshed_after_confirmations, "blockNumber"
            )
            refreshed_block = (
                int(refreshed_block_raw) if refreshed_block_raw is not None else 0
            )
            if refreshed_block != block_number:
                raise AnchorVerificationError(
                    "reorg detected: transaction moved to different block"
                )

        final_hash = self._normalize_block_hash(
            self._receipt_field(latest_receipt, "blockHash")
        )
        if (
            initial_block_hash is not None
            and final_hash is not None
            and initial_block_hash != final_hash
        ):
            raise AnchorVerificationError(
                "reorg detected: receipt block hash changed during confirmation window"
            )

        if final_hash is not None:
            block = self._web3.eth.get_block(block_number)
            block_hash = (
                block.get("hash")
                if isinstance(block, dict)
                else getattr(block, "hash", None)
            )
            canonical_block_hash = self._normalize_block_hash(block_hash)
            if canonical_block_hash is not None and canonical_block_hash != final_hash:
                raise AnchorVerificationError(
                    "reorg detected: canonical block hash mismatch"
                )

        return latest_receipt

    def _decode_hash_from_transaction_input(self, tx_hash: str) -> str | None:
        getter = getattr(self._web3.eth, "get_transaction", None)
        if not callable(getter):
            return None
        inputs = self._function_abi.get("inputs", [])
        if not inputs or not isinstance(inputs[0], dict):
            return None
        first_type = str(inputs[0].get("type", "")).lower()
        if first_type != "bytes32":
            return None

        try:
            tx = getter(tx_hash)
        except Exception:
            return None

        if isinstance(tx, dict):
            input_data = tx.get("input") or tx.get("data")
        else:
            input_data = getattr(tx, "input", None) or getattr(tx, "data", None)
        if not isinstance(input_data, str):
            return None
        raw = input_data[2:] if input_data.startswith("0x") else input_data
        if len(raw) < (8 + 64):
            return None
        encoded_first_arg = raw[8:72]
        return _normalize_hash(encoded_first_arg)

    def _build_function_args(self, *, event_id: int, canonical_hash: str) -> list[Any]:
        args: list[Any] = []
        for parameter in self._function_abi.get("inputs", []):
            if not isinstance(parameter, dict):
                raise AnchorAdapterError("invalid ABI input definition")
            input_type = str(parameter.get("type", "")).strip().lower()
            if input_type == "bytes32":
                args.append(_hash_bytes32(canonical_hash))
                continue
            if input_type == "bytes":
                args.append(_hash_bytes32(canonical_hash))
                continue
            if input_type.startswith("uint") or input_type.startswith("int"):
                args.append(event_id)
                continue
            if input_type == "string":
                args.append(_normalize_hash(canonical_hash))
                continue
            raise AnchorAdapterError(
                f"unsupported contract function input type: {input_type}"
            )
        return args

    def _to_hex(self, value: Any) -> str:
        if isinstance(value, str):
            return value if value.startswith("0x") else f"0x{value}"
        if isinstance(value, (bytes, bytearray)):
            return f"0x{bytes(value).hex()}"
        if hasattr(value, "hex") and callable(value.hex):
            rendered = value.hex()
            if isinstance(rendered, str):
                return rendered if rendered.startswith("0x") else f"0x{rendered}"
        raise AnchorAdapterError("unable to convert transaction hash to hex")

    def _receipt_field(self, receipt: Any, name: str) -> Any:
        if isinstance(receipt, dict):
            return receipt.get(name)
        return getattr(receipt, name, None)

    def _decode_hash_from_event(self, receipt: Any) -> str | None:
        if not self._event_name:
            return None
        event_factory = getattr(self._contract.events, self._event_name, None)
        if event_factory is None:
            return None
        try:
            entries = event_factory().process_receipt(receipt)
        except Exception:
            return None

        candidate_keys = ("canonicalHash", "hash", "eventHash", "dataHash")
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            args = entry.get("args")
            if not isinstance(args, dict):
                continue
            for key in candidate_keys:
                if key not in args:
                    continue
                value = args[key]
                if isinstance(value, (bytes, bytearray)):
                    return _normalize_hash(bytes(value).hex())
                if hasattr(value, "hex") and callable(value.hex):
                    rendered = value.hex()
                    if isinstance(rendered, str):
                        return _normalize_hash(rendered)
                if isinstance(value, str):
                    return _normalize_hash(value)
        return None

    def anchor_event(
        self,
        *,
        event_id: int,
        canonical_hash: str,
        payload: dict[str, Any],
    ) -> AnchorSubmission:
        del payload
        normalized_hash = _normalize_hash(canonical_hash)

        function_callable = getattr(self._contract.functions, self._function_name, None)
        if function_callable is None:
            raise AnchorAdapterError(
                f"contract function '{self._function_name}' not available"
            )

        args = self._build_function_args(
            event_id=event_id, canonical_hash=normalized_hash
        )
        fn_call = function_callable(*args)

        try:
            nonce = int(
                self._web3.eth.get_transaction_count(self._account_address, "pending")
            )
        except Exception as exc:
            raise AnchorAdapterError("failed to fetch account nonce") from exc

        resolved_chain_id = self._chain_id
        if resolved_chain_id is None:
            try:
                resolved_chain_id = int(self._web3.eth.chain_id)
            except Exception as exc:
                raise AnchorAdapterError("failed to determine chain id") from exc

        tx: dict[str, Any] = {
            "from": self._account_address,
            "nonce": nonce,
            "chainId": resolved_chain_id,
        }
        try:
            estimated = int(fn_call.estimate_gas({"from": self._account_address}))
            tx["gas"] = max(estimated, self._gas_limit)
        except Exception:
            tx["gas"] = self._gas_limit

        tx_hash = self._submit_with_fee_fallback(fn_call, tx)

        self._submitted[tx_hash] = _TxContext(
            event_id=event_id, canonical_hash=normalized_hash
        )
        return AnchorSubmission(
            transaction_hash=tx_hash,
            network=self._network,
            metadata={
                "adapter": "evm_contract",
                "contract_address": self._contract_address,
                "function": self._function_name,
                "event_id": event_id,
                "chain_id": resolved_chain_id,
            },
        )

    def get_receipt(self, transaction_hash: str) -> AnchorReceiptData:
        tx_hash = self._to_hex(transaction_hash)
        try:
            receipt = self._web3.eth.wait_for_transaction_receipt(
                tx_hash,
                timeout=self._receipt_timeout_seconds,
                poll_latency=self._poll_interval_seconds,
            )
        except Exception as exc:
            raise AnchorTimeoutError(
                f"timed out waiting for transaction receipt: {tx_hash}"
            ) from exc

        receipt = self._wait_for_confirmations(tx_hash, receipt)

        status_raw = self._receipt_field(receipt, "status")
        status_code = int(status_raw) if status_raw is not None else 0
        block_number_raw = self._receipt_field(receipt, "blockNumber")
        block_number = int(block_number_raw) if block_number_raw is not None else 0
        latest_block_number = self._latest_block_number()
        confirmations = (
            max(0, latest_block_number - block_number + 1) if block_number > 0 else 0
        )

        anchored_at = self._now_fn()
        if block_number > 0:
            try:
                block = self._web3.eth.get_block(block_number)
                block_timestamp = (
                    block.get("timestamp")
                    if isinstance(block, dict)
                    else getattr(block, "timestamp", None)
                )
                if block_timestamp is not None:
                    anchored_at = _to_utc_datetime(int(block_timestamp))
            except Exception:
                anchored_at = self._now_fn()

        decoded_hash = self._decode_hash_from_event(receipt)
        if decoded_hash is None:
            decoded_hash = self._decode_hash_from_transaction_input(tx_hash)
        if decoded_hash is None:
            cached = self._submitted.get(tx_hash)
            decoded_hash = cached.canonical_hash if cached is not None else None

        payload = {
            "network": self._network,
            "transaction_hash": tx_hash,
            "block_number": block_number,
            "block_hash": self._normalize_block_hash(
                self._receipt_field(receipt, "blockHash")
            ),
            "confirmations": confirmations,
            "status": "success" if status_code == 1 else "reverted",
            "status_code": status_code,
            "gas_used": int(self._receipt_field(receipt, "gasUsed") or 0),
            "effective_gas_price": int(
                self._receipt_field(receipt, "effectiveGasPrice") or 0
            ),
            "transaction_index": int(
                self._receipt_field(receipt, "transactionIndex") or 0
            ),
            "canonical_hash": decoded_hash,
        }
        return AnchorReceiptData(
            transaction_hash=tx_hash,
            network=self._network,
            anchored_at=anchored_at,
            receipt_payload=payload,
        )

    def verify_anchor(
        self, *, canonical_hash: str, receipt: AnchorReceiptData | None
    ) -> bool:
        if receipt is None:
            return False
        expected = _normalize_hash(canonical_hash)
        payload_hash = receipt.receipt_payload.get("canonical_hash")
        if isinstance(payload_hash, str):
            candidate = _normalize_hash(payload_hash)
        else:
            cached = self._submitted.get(receipt.transaction_hash)
            if cached is None:
                return False
            candidate = cached.canonical_hash
        status = str(receipt.receipt_payload.get("status", "")).lower()
        return status == "success" and candidate == expected
