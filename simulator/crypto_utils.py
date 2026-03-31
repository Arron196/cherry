"""ATECC608A secure element simulator -- ECDSA + SHA-256 utilities."""

from __future__ import annotations

import base64
import hashlib
import json

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec


class ATECC608ASimulator:
    """Simulate the Microchip ATECC608A security chip (ECC P-256)."""

    def __init__(self) -> None:
        self.private_key: ec.EllipticCurvePrivateKey | None = None
        self.public_key: ec.EllipticCurvePublicKey | None = None

    # ------------------------------------------------------------------
    # Key management
    # ------------------------------------------------------------------

    def generate_keypair(self) -> str:
        """Generate an ECC P-256 key pair and return the PEM public key."""
        self.private_key = ec.generate_private_key(ec.SECP256R1())
        self.public_key = self.private_key.public_key()
        return self.get_public_key_pem()

    def get_public_key_pem(self) -> str:
        """Return the public key in PEM format."""
        if self.public_key is None:
            raise RuntimeError("Key pair not generated yet -- call generate_keypair() first")
        return self.public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

    # ------------------------------------------------------------------
    # Signing / hashing
    # ------------------------------------------------------------------

    def sign_data(self, data: bytes) -> str:
        """Sign *data* with ECDSA-P256-SHA256, return a base64-encoded signature."""
        if self.private_key is None:
            raise RuntimeError("Key pair not generated yet -- call generate_keypair() first")
        raw_signature = self.private_key.sign(data, ec.ECDSA(hashes.SHA256()))
        return base64.b64encode(raw_signature).decode("utf-8")

    @staticmethod
    def compute_sha256(data: bytes) -> str:
        """Return the hex-encoded SHA-256 digest of *data*."""
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def compute_sha256_json(obj: dict) -> str:
        """Canonical JSON -> SHA-256 hex digest."""
        canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
