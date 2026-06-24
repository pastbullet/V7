"""Run unit readings from a materialized discovery result."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path
from typing import Any

from src.reading.runner import run_reading_claim_agent


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_dir_name(unit_id: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", unit_id.strip())
    return text.strip("._") or "unit"


def _compact_refs(refs: Any) -> str:
    if not isinstance(refs, list) or not refs:
        return "[]"
    compact: list[dict[str, Any]] = []
    for item in refs[:8]:
        if isinstance(item, dict):
            compact.append(
                {
                    key: item[key]
                    for key in ("type", "span_id", "asset_id", "cell_id", "quote")
                    if key in item
                }
            )
    return json.dumps(compact, ensure_ascii=False)


def _build_reading_goal_from_unit(unit: dict[str, Any]) -> str:
    title = str(unit.get("title") or unit.get("unit_id") or "").strip()
    kind = str(unit.get("kind") or "protocol_unit").strip()
    reason = str(unit.get("reason") or "").strip()
    evidence = _compact_refs(unit.get("evidence_refs"))
    assets = _compact_refs(unit.get("related_assets"))
    return (
        f"Read this discovered specification unit: {title}\n"
        f"Unit kind: {kind}\n"
        f"Discovery reason: {reason}\n"
        f"Discovery evidence refs: {evidence}\n"
        f"Related asset ids: {assets}\n\n"
        "Produce atomic claims for later IR extraction. Keep facts grounded in raw span/cell/crop refs."
    )


async def run_readings_from_discovery(
    *,
    discovery_path: str | Path,
    output_dir: str | Path,
    model: str | None = None,
    max_turns: int = 25,
) -> dict[str, Any]:
    """Run the reading agent for every unit in ``discovered_units.json``."""
    discovery_file = Path(discovery_path)
    discovery = _read_json(discovery_file)
    doc_id = str(discovery.get("doc_id") or "").strip()
    if not doc_id:
        raise ValueError("discovered_units.json must contain doc_id")
    units = discovery.get("units")
    if not isinstance(units, list):
        units = []

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    manifest_units: list[dict[str, Any]] = []
    totals = {
        "accepted_claim_count": 0,
        "unresolved_count": 0,
        "invalid_count": 0,
        "llm_turns": 0,
    }

    for raw_unit in units:
        if not isinstance(raw_unit, dict):
            continue
        unit_id = str(raw_unit.get("unit_id") or "").strip()
        if not unit_id:
            continue
        unit_out = out / _safe_dir_name(unit_id)
        result = await run_reading_claim_agent(
            doc_name=doc_id,
            unit_id=unit_id,
            reading_goal=_build_reading_goal_from_unit(raw_unit),
            output_dir=unit_out,
            model=model,
            max_turns=max_turns,
        )
        accepted = int(result.get("accepted_count", 0) or 0)
        unresolved = int(result.get("unresolved_count", 0) or 0)
        invalid = int(result.get("invalid_count", 0) or 0)
        turns = int(result.get("llm_turns", 0) or 0)
        totals["accepted_claim_count"] += accepted
        totals["unresolved_count"] += unresolved
        totals["invalid_count"] += invalid
        totals["llm_turns"] += turns
        manifest_units.append(
            {
                "unit_id": unit_id,
                "title": raw_unit.get("title"),
                "kind": raw_unit.get("kind"),
                "reading_dir": str(unit_out),
                "accepted_count": accepted,
                "unresolved_count": unresolved,
                "invalid_count": invalid,
                "llm_turns": turns,
            }
        )

    manifest = {
        "doc_id": doc_id,
        "discovery_path": str(discovery_file),
        "unit_count": len(manifest_units),
        "units": manifest_units,
        "totals": totals,
    }
    _write_json(out / "reading_manifest.json", manifest)

    return {
        "output_dir": str(out),
        "unit_count": len(manifest_units),
        **totals,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run SpecIndex readings from discovered units.")
    parser.add_argument("--discovery", required=True, help="Path to discovered_units.json.")
    parser.add_argument("--out", required=True, help="Output directory for per-unit readings.")
    parser.add_argument("--model", default=None, help="Optional LLM model name.")
    parser.add_argument("--max-turns", type=int, default=25)
    args = parser.parse_args(argv)

    result = asyncio.run(
        run_readings_from_discovery(
            discovery_path=args.discovery,
            output_dir=args.out,
            model=args.model,
            max_turns=args.max_turns,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

