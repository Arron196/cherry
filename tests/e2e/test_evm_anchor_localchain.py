from __future__ import annotations

import json
import os
import importlib
from typing import Any

import pytest

from app.services.anchor_adapter.evm_contract import EvmContractAnchorAdapter


def _env_or_default(name: str, default: str) -> str:
    value = os.getenv(name, "").strip()
    return value or default


def _normalize_private_key(value: str) -> str:
    key = value.strip()
    return key if key.startswith("0x") else f"0x{key}"


def _expected_backend() -> str:
    expected = os.getenv("EVM_E2E_EXPECT_BACKEND", "anvil-local").strip()
    if expected not in {"anvil-local", "eth-tester-local"}:
        raise AssertionError(
            "EVM_E2E_EXPECT_BACKEND must be one of: anvil-local, eth-tester-local"
        )
    return expected


def _build_local_chain_client(
    web3_module: object,
) -> tuple[Any, str, str, str | None]:
    web3_class = getattr(web3_module, "Web3")
    rpc_url = _env_or_default("ANVIL_RPC_URL", "http://127.0.0.1:8545")
    private_key = _normalize_private_key(
        _env_or_default(
            "ANVIL_PRIVATE_KEY",
            "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
        )
    )

    web3 = web3_class(web3_class.HTTPProvider(rpc_url))
    if web3.is_connected():
        return web3, private_key, "anvil-local", rpc_url

    try:
        ethereum_tester_provider = getattr(web3_module, "EthereumTesterProvider", None)
        if ethereum_tester_provider is None:
            provider_module = importlib.import_module("web3.providers.eth_tester")
            ethereum_tester_provider = getattr(
                provider_module, "EthereumTesterProvider"
            )

        eth_tester_module = importlib.import_module("eth_tester")
        py_evm_backend = getattr(eth_tester_module, "PyEVMBackend")
        ethereum_tester = getattr(eth_tester_module, "EthereumTester")
    except Exception as exc:
        raise RuntimeError(
            "eth-tester with py-evm is required when ANVIL RPC is unavailable"
        ) from exc

    backend = py_evm_backend()
    tester = ethereum_tester(backend=backend)
    web3 = web3_class(ethereum_tester_provider(tester))
    if not web3.is_connected():
        raise RuntimeError("failed to initialize in-process eth-tester backend")

    account_keys = list(getattr(backend, "account_keys", []))
    if not account_keys:
        raise RuntimeError("eth-tester backend did not expose funded account keys")

    first_key = account_keys[0]
    if hasattr(first_key, "to_hex") and callable(first_key.to_hex):
        fallback_private_key = str(first_key.to_hex())
    elif hasattr(first_key, "hex") and callable(first_key.hex):
        fallback_private_key = str(first_key.hex())
    else:
        raise RuntimeError(
            "unable to derive funded private key from eth-tester backend"
        )

    return web3, _normalize_private_key(fallback_private_key), "eth-tester-local", None


@pytest.mark.e2e
def test_evm_anchor_end_to_end_local_chain() -> None:
    if os.getenv("RUN_EVM_E2E") != "1":
        pytest.skip("set RUN_EVM_E2E=1 to run local-chain e2e")

    try:
        solcx_module = importlib.import_module("solcx")
    except Exception as exc:
        raise RuntimeError("py-solc-x is required for EVM e2e test") from exc

    web3_module = importlib.import_module("web3")
    web3, private_key, network_name, rpc_url = _build_local_chain_client(web3_module)
    expected_backend = _expected_backend()
    assert network_name == expected_backend, (
        "EVM e2e backend mismatch: "
        f"expected '{expected_backend}' via EVM_E2E_EXPECT_BACKEND, "
        f"but selected '{network_name}'. "
        "Set EVM_E2E_EXPECT_BACKEND explicitly to match intended backend."
    )

    account = web3.eth.account.from_key(private_key)
    chain_id = int(web3.eth.chain_id)

    source = """
    // SPDX-License-Identifier: MIT
    pragma solidity ^0.8.24;

    contract AnchorRegistry {
        event HashAnchored(bytes32 indexed canonicalHash, uint256 eventId);

        function anchorEvent(bytes32 canonicalHash, uint256 eventId) external {
            emit HashAnchored(canonicalHash, eventId);
        }
    }
    """

    set_solc_version = getattr(solcx_module, "set_solc_version")
    compile_source = getattr(solcx_module, "compile_source")
    install_solc = getattr(solcx_module, "install_solc", None)
    try:
        set_solc_version("0.8.24")
    except Exception:
        if install_solc is None:
            raise
        install_solc("0.8.24")
        set_solc_version("0.8.24")
    compiled = compile_source(source, output_values=["abi", "bin"])
    contract_interface = compiled["<stdin>:AnchorRegistry"]
    contract = web3.eth.contract(
        abi=contract_interface["abi"],
        bytecode=contract_interface["bin"],
    )

    nonce = int(web3.eth.get_transaction_count(account.address, "pending"))
    deploy_tx = contract.constructor().build_transaction(
        {
            "from": account.address,
            "nonce": nonce,
            "chainId": chain_id,
            "gas": 1_200_000,
            "gasPrice": int(web3.eth.gas_price),
        }
    )
    signed = web3.eth.account.sign_transaction(deploy_tx, private_key=private_key)
    deploy_hash = web3.eth.send_raw_transaction(signed.raw_transaction)
    deploy_receipt = web3.eth.wait_for_transaction_receipt(deploy_hash, timeout=60)
    contract_address = str(deploy_receipt["contractAddress"])

    if rpc_url is not None:
        adapter = EvmContractAnchorAdapter(
            rpc_url=rpc_url,
            web3_client=web3,
            contract_address=contract_address,
            contract_abi_json=json.dumps(contract_interface["abi"]),
            function_name="anchorEvent",
            event_name="HashAnchored",
            network=network_name,
            chain_id=chain_id,
            account_address=account.address,
            private_key=private_key,
            receipt_timeout_seconds=60,
            poll_interval_seconds=1,
            gas_limit=250_000,
        )
    else:
        adapter = EvmContractAnchorAdapter(
            web3_client=web3,
            contract_address=contract_address,
            contract_abi_json=json.dumps(contract_interface["abi"]),
            function_name="anchorEvent",
            event_name="HashAnchored",
            network=network_name,
            chain_id=chain_id,
            account_address=account.address,
            private_key=private_key,
            receipt_timeout_seconds=60,
            poll_interval_seconds=1,
            gas_limit=250_000,
        )

    canonical_hash = "a" * 64
    submission = adapter.anchor_event(
        event_id=42,
        canonical_hash=canonical_hash,
        payload={"source": "e2e"},
    )
    receipt = adapter.get_receipt(submission.transaction_hash)

    assert submission.network == network_name
    assert submission.transaction_hash.startswith("0x")
    assert receipt.transaction_hash == submission.transaction_hash
    assert int(receipt.receipt_payload.get("block_number", 0)) > 0
    assert str(receipt.receipt_payload.get("block_hash", "")).startswith("0x")
    assert receipt.receipt_payload["status"] == "success"
    assert int(receipt.receipt_payload.get("confirmations", 0)) >= 1
    assert receipt.receipt_payload.get("canonical_hash") == f"0x{canonical_hash}"
    assert adapter.verify_anchor(canonical_hash=canonical_hash, receipt=receipt) is True
