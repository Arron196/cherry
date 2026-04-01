from app.domain.contracts.hash_canonicalization import canonical_hash


def test_canonical_hash_is_deterministic_for_fixed_fixture() -> None:
    fixture = {
        "batch_id": "batch-2026-02-10",
        "device_id": "device-001",
        "sensor_payload": {
            "humidity_pct": 73.0,
            "temperature_c": 4.2,
            "flags": ["stable", "cooled"],
        },
        "signature_envelope": {
            "signature": "MEUCIQCFIXEDTESTSIGNATURE==",
            "key_id": "factory-key-1",
            "algorithm": "ECDSA_P256_SHA256",
        },
        "timestamp": "2026-02-10T02:00:00+00:00",
        "version": "1.0.0",
    }

    reordered_fixture = {
        "version": "1.0.0",
        "timestamp": "2026-02-10T02:00:00+00:00",
        "signature_envelope": {
            "algorithm": "ECDSA_P256_SHA256",
            "key_id": "factory-key-1",
            "signature": "MEUCIQCFIXEDTESTSIGNATURE==",
        },
        "sensor_payload": {
            "flags": ["stable", "cooled"],
            "temperature_c": 4.2,
            "humidity_pct": 73.0,
        },
        "device_id": "device-001",
        "batch_id": "batch-2026-02-10",
    }

    expected = "be20a11500e85b75553b7465b50140f424fe1efac0b2be67f3d6dc070a11ce2c"

    assert canonical_hash(fixture) == expected
    assert canonical_hash(reordered_fixture) == expected
