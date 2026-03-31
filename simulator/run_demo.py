#!/usr/bin/env python3
"""
Cherry cold-chain STM32 device simulator -- demo entry point.

Simulates two STM32H743 devices (storage + transport) collecting sensor
data, signing it with HMAC-SHA256, and posting TraceEvents to the backend.

Usage:
    python -m simulator.run_demo [--api-url URL] [--count N] [--interval SEC]
"""

from __future__ import annotations

import argparse

from .gateway import EdgeGateway
from .storage_device import StorageDevice
from .transport_device import TransportDevice


# ---------------------------------------------------------------------------
# Defaults -- must match INGEST_SIGNING_KEYS in the backend .env
# ---------------------------------------------------------------------------
DEFAULT_API_URL = "http://localhost:18941"
DEFAULT_KEY_ID = "factory-key-1"
DEFAULT_SECRET = "super-secret"


def run_demo(
    api_url: str = DEFAULT_API_URL,
    count: int = 10,
    interval: float = 2.0,
    key_id: str = DEFAULT_KEY_ID,
    secret: str = DEFAULT_SECRET,
    ingest_mode: str = "canonical",
) -> None:
    print("=" * 60)
    print("  Cherry Cold-Chain  --  STM32 Device Simulator")
    print("=" * 60)
    print(f"Backend URL : {api_url}")
    print(f"Signing key : {key_id}")
    print(f"Ingest mode : {ingest_mode}")
    print(f"Readings    : {count} per device, {interval}s interval")
    print()

    # ---- Edge gateway (holds device public keys) ----
    gateway = EdgeGateway(api_url=api_url, ingest_mode=ingest_mode)

    # ---- Storage device (cold warehouse) ----
    storage = StorageDevice(
        device_id="STM32-STORAGE-001",
        gateway_url=api_url,
        signing_key_id=key_id,
        signing_secret=secret,
        ingest_mode=ingest_mode,
    )
    pub_key = storage.crypto.generate_keypair()
    gateway.register_device(storage.device_id, pub_key)

    # ---- Transport device (refrigerated truck) ----
    transport = TransportDevice(
        device_id="STM32-TRANSPORT-001",
        gateway_url=api_url,
        signing_key_id=key_id,
        signing_secret=secret,
        ingest_mode=ingest_mode,
    )
    pub_key = transport.crypto.generate_keypair()
    gateway.register_device(transport.device_id, pub_key)

    # ---- Run collection loops ----
    print("\n>>> Phase 1: Cold Storage Monitoring")
    print(f"    Batch ID: {storage.batch_id}")
    storage_results = storage.run(interval_seconds=interval, count=count)

    print("\n>>> Phase 2: Refrigerated Transport Monitoring")
    print(f"    Batch ID: {transport.batch_id}")
    transport_results = transport.run(interval_seconds=interval, count=count)

    # ---- Summary ----
    total = len(storage_results) + len(transport_results)
    print("\n" + "=" * 60)
    print("  SIMULATION COMPLETE")
    print("=" * 60)
    print(f"Storage  device : {len(storage_results)}/{count} events sent")
    print(f"Transport device: {len(transport_results)}/{count} events sent")
    print(f"Total events    : {total}")
    print()

    if total > 0:
        print("Traceability query links:")
        print(f"  Storage batch  : {api_url}/v1/trace/{storage.batch_id}")
        print(f"  Transport batch: {api_url}/v1/trace/{transport.batch_id}")
    else:
        print("[WARN] No events were accepted. Is the backend running?")
        print(f"  Ensure the server is up at {api_url}")
        print(f'  Ensure INGEST_SIGNING_KEYS contains "{key_id}"')


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cherry cold-chain STM32 device simulator"
    )
    parser.add_argument(
        "--api-url", default=DEFAULT_API_URL, help="Backend API base URL"
    )
    parser.add_argument(
        "--count", type=int, default=10, help="Number of readings per device"
    )
    parser.add_argument(
        "--interval", type=float, default=2.0, help="Seconds between readings"
    )
    parser.add_argument("--key-id", default=DEFAULT_KEY_ID, help="HMAC signing key ID")
    parser.add_argument("--secret", default=DEFAULT_SECRET, help="HMAC signing secret")
    parser.add_argument(
        "--ingest-mode",
        choices=["compat", "canonical"],
        default="canonical",
        help="Telemetry ingest route mode",
    )
    args = parser.parse_args()

    run_demo(
        api_url=args.api_url,
        count=args.count,
        interval=args.interval,
        key_id=args.key_id,
        secret=args.secret,
        ingest_mode=args.ingest_mode,
    )


if __name__ == "__main__":
    main()
