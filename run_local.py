"""
Local development runner for Cherry Traceability System.
Usage: python run_local.py
"""

import os
import sys

os.environ.setdefault("TRACEABILITY_DATABASE_URL", "sqlite:///./data/app.db")
os.environ.setdefault(
    "INGEST_SIGNING_KEYS",
    '{"factory-key-1":"super-secret","storage-device-1":"storage-secret","transport-device-1":"transport-secret"}',
)
os.environ.setdefault("ANCHOR_ADAPTER", "active_mock")
os.environ.setdefault("ANCHOR_MOCK_MODE", "success")
os.environ.setdefault("ANCHOR_EVM_ROLLOUT_MODE", "rollback_safe")
os.environ.setdefault("ANCHOR_EVM_CANARY_PERCENT", "5")
os.environ.setdefault("ANCHOR_EVM_FORCE_ROLLBACK_SAFE", "0")
os.environ.setdefault("ANCHOR_EVM_CANARY_MIN_SUCCESS_RATE", "0.99")
os.environ.setdefault("ANCHOR_EVM_CANARY_MAX_DEAD_LETTER_RATE", "0.005")
os.environ.setdefault("ANCHOR_EVM_CANARY_MAX_P95_CONFIRMATION_SECONDS", "120")
os.environ.setdefault("ANCHOR_EVM_CANARY_ABORT_AFTER_SECONDS", "600")
os.environ.setdefault("ANCHOR_EVM_CANARY_WINDOW_SECONDS", "600")
os.environ.setdefault("AUTH_JWT_SECRET", "dev-auth-secret")
os.environ.setdefault(
    "AUTH_DEMO_CREDENTIALS",
    '{"admin":{"password":"admin123","role":"admin"},"regulator":{"password":"regulator123","role":"regulator"}}',
)
os.environ.setdefault("CORS_ALLOW_ORIGINS", "*")


if __name__ == "__main__":
    import uvicorn
    from alembic.config import Config
    from alembic import command

    os.makedirs("data", exist_ok=True)

    print("=" * 60)
    print("  Cherry Traceability System - Local Dev Server")
    print("=" * 60)
    print("  Backend:  http://localhost:18941")
    print("  API Docs: http://localhost:18941/docs")
    print("  Login:    admin / admin123")
    print("  Simulator: python -m simulator.run_demo")
    print("  Frontend:  cd frontend && npm run dev")
    print("  Tests:     .venv\\Scripts\\python.exe -m pytest tests/integration/test_hardware_ingest_migration_modes.py -q")
    print("=" * 60)

    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    print("[OK] Database migrations completed.")

    uvicorn.run("app.main:app", host="0.0.0.0", port=18941, reload=True)
