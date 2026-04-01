from __future__ import annotations

import copy
import json
from pathlib import Path

from app.main import app
from scripts import contract_guard


def _guard_result_payload(output: str) -> dict[str, object]:
    lines = [
        line
        for line in output.splitlines()
        if line.startswith("CONTRACT_GUARD_RESULT ")
    ]
    assert lines
    return json.loads(lines[-1].split(" ", 1)[1])


def test_contract_guard_passes_migration_surface_baseline(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.delenv("CONTRACT_GUARD_OPENAPI_OVERRIDE", raising=False)

    exit_code = contract_guard.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    result = _guard_result_payload(output)
    assert result["status"] == "PASS"
    assert result["checked"] == "openapi+migration_surface"


def test_contract_guard_fails_when_migration_surface_schema_drifts(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    drifted_openapi = copy.deepcopy(app.openapi())

    paths = drifted_openapi.get("paths")
    assert isinstance(paths, dict)
    paths.pop("/v1/public/trace/{batch_id}", None)

    components = drifted_openapi.get("components")
    assert isinstance(components, dict)
    schemas = components.get("schemas")
    assert isinstance(schemas, dict)
    overview_schema = schemas.get("OverviewResponse")
    assert isinstance(overview_schema, dict)
    required = overview_schema.get("required")
    assert isinstance(required, list)
    overview_schema["required"] = [
        field for field in required if field != "open_alerts"
    ]

    override_path = tmp_path / "drifted-openapi.json"
    override_path.write_text(json.dumps(drifted_openapi), encoding="utf-8")
    monkeypatch.setenv("CONTRACT_GUARD_OPENAPI_OVERRIDE", str(override_path))

    exit_code = contract_guard.main()
    output = capsys.readouterr().out

    assert exit_code == 1
    result = _guard_result_payload(output)
    assert result["status"] == "FAIL"
    count = result.get("count")
    assert isinstance(count, int)
    assert count >= 2
    assert "Missing required path: /v1/public/trace/{batch_id}" in output
    assert "OverviewResponse schema must require `open_alerts`" in output
