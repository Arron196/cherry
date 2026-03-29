from __future__ import annotations

import json
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = PROJECT_ROOT / "docs" / "CONTRACT_V1_MIGRATION.md"
FE_SERVICES_PATH = PROJECT_ROOT / "frontend" / "src" / "lib" / "services.ts"
HW_PATH = PROJECT_ROOT / "hardware" / "cherry" / "Core" / "Src" / "cherry_hw.c"
SIMULATOR_PATHS = (
    PROJECT_ROOT / "simulator" / "stm32_device.py",
    PROJECT_ROOT / "simulator" / "gateway.py",
)


REQUIRED_SECTIONS = (
    "## Canonical Baselines",
    "## Canonical-to-Compatibility Field Mapping",
    "## Endpoint Mapping Table (FE/HW -> Canonical and Compat)",
    "## Endpoint Map",
    "## Compatibility Deprecation Schedule",
    "## Exit Criteria",
    "## Rollback Note",
)


REQUIRED_KEYWORDS = (
    "app/domain/contracts/trace_event.py",
    "app/api/public_trace.py",
    "app/api/stats.py",
    "ECDSA_P256_SHA256",
    "`ECDSA`",
    "normaliz",
    "2 releases",
    "14 consecutive days",
    "<1% compat traffic",
    "batch_info",
    "timeline",
    "stage_environments",
    "quality",
    "blockchain_anchor",
)


def _normalize_endpoint(raw: str) -> str:
    endpoint = raw.strip().strip("`\"'")
    replacements = {
        "${batchId}": "{batch_id}",
        "${alertId}": "{alert_id}",
        "${ingestRequestId}": "{ingest_request_id}",
        "${deviceId}": "{device_id}",
        "${policyId}": "{policy_id}",
        "${encodeURIComponent(policyId)}": "{policy_id}",
    }
    for source, target in replacements.items():
        endpoint = endpoint.replace(source, target)
    endpoint = re.sub(r"\$\{[^}]+\}", "{param}", endpoint)
    endpoint = endpoint.replace("//", "/")
    return endpoint


def _extract_fe_endpoints(fe_services: Path) -> set[str]:
    text = fe_services.read_text(encoding="utf-8")
    pattern = re.compile(
        r"api\.(?:get|post|put|delete|patch)\s*(?:<[^>]+>)?\s*\(\s*([`\"'])(.+?)\1",
        re.DOTALL,
    )
    endpoints: set[str] = set()
    for _, raw in pattern.findall(text):
        cleaned = _normalize_endpoint(raw)
        if cleaned.startswith("/"):
            endpoints.add(cleaned)
    return endpoints


def _extract_hw_endpoints(hw_path: Path, simulator_paths: tuple[Path, ...]) -> set[str]:
    endpoints: set[str] = set()

    hw_text = hw_path.read_text(encoding="utf-8")
    hw_match = re.search(r'#define\s+CHERRY_HTTP_PATH\s+"([^"]+)"', hw_text)
    if hw_match:
        endpoints.add(_normalize_endpoint(hw_match.group(1)))

    fstring_pattern = re.compile(r"\{[^}]+\}(/v1/[A-Za-z0-9_/{}/.-]+)")
    for path in simulator_paths:
        sim_text = path.read_text(encoding="utf-8")
        for endpoint in fstring_pattern.findall(sim_text):
            endpoints.add(_normalize_endpoint(endpoint))

    return endpoints


def _section_slice(document: str, title: str, next_title: str | None = None) -> str:
    start = document.find(title)
    if start < 0:
        return ""
    if next_title is None:
        return document[start:]
    end = document.find(next_title, start + len(title))
    if end < 0:
        return document[start:]
    return document[start:end]


def main() -> int:
    failures: list[str] = []

    if not DOC_PATH.exists():
        print(
            "CONTRACT_SPEC_RESULT",
            json.dumps(
                {"status": "FAIL", "reason": f"missing file: {DOC_PATH.as_posix()}"}
            ),
        )
        return 1

    document = DOC_PATH.read_text(encoding="utf-8")

    for section in REQUIRED_SECTIONS:
        if section not in document:
            failures.append(f"missing section heading: {section}")

    doc_lower = document.lower()
    for keyword in REQUIRED_KEYWORDS:
        if keyword.lower() not in doc_lower:
            failures.append(f"missing required keyword: {keyword}")

    mapping_section = _section_slice(
        document,
        "## Endpoint Mapping Table (FE/HW -> Canonical and Compat)",
        "## Endpoint Map",
    )
    if not mapping_section:
        failures.append("mapping table section is empty or missing")
    else:
        fe_endpoints = _extract_fe_endpoints(FE_SERVICES_PATH)
        hw_endpoints = _extract_hw_endpoints(HW_PATH, SIMULATOR_PATHS)

        uncovered_fe = sorted(ep for ep in fe_endpoints if ep not in mapping_section)
        uncovered_hw = sorted(ep for ep in hw_endpoints if ep not in mapping_section)

        if uncovered_fe:
            failures.append(
                "unmapped FE endpoints in mapping table: " + ", ".join(uncovered_fe)
            )
        if uncovered_hw:
            failures.append(
                "unmapped HW endpoints in mapping table: " + ", ".join(uncovered_hw)
            )

    if failures:
        print(
            "CONTRACT_SPEC_RESULT",
            json.dumps({"status": "FAIL", "count": len(failures)}),
        )
        for issue in failures:
            print(f"- {issue}")
        return 1

    summary = {
        "status": "PASS",
        "doc": DOC_PATH.as_posix(),
        "fe_endpoints_checked": len(_extract_fe_endpoints(FE_SERVICES_PATH)),
        "hw_endpoints_checked": len(_extract_hw_endpoints(HW_PATH, SIMULATOR_PATHS)),
    }
    print("CONTRACT_SPEC_RESULT", json.dumps(summary, ensure_ascii=False))
    print("CONTRACT_SPEC_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
