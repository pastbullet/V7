"""Materialize LLM-proposed protocol units into auditable discovery artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.tools.specindex_assets import get_image, get_table, verify_evidence


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_evidence_refs(raw: Any) -> list[dict[str, Any]]:
    return raw if isinstance(raw, list) else []


def _normalize_related_assets(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    assets: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        asset_id = str(item.get("asset_id") or "").strip()
        asset_type = str(item.get("type") or item.get("asset_type") or "").strip()
        if not asset_id:
            continue
        assets.append({"type": asset_type, "asset_id": asset_id})
    return assets


def _normalize_candidate(raw: dict[str, Any], index: int) -> dict[str, Any]:
    unit_id = str(raw.get("unit_id") or f"unit_{index:04d}").strip()
    title = str(raw.get("title") or unit_id).strip()
    return {
        **raw,
        "unit_id": unit_id,
        "title": title,
        "kind": str(raw.get("kind") or "protocol_unit").strip(),
        "reason": str(raw.get("reason") or "").strip(),
        "status": str(raw.get("status") or "accepted").strip(),
        "evidence_refs": _normalize_evidence_refs(raw.get("evidence_refs")),
        "related_assets": _normalize_related_assets(raw.get("related_assets")),
    }


def _unresolved_item(candidate: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "unit_id": candidate["unit_id"],
        "title": candidate["title"],
        "kind": candidate["kind"],
        "reason": reason,
        "evidence_refs": candidate["evidence_refs"],
        "related_assets": candidate["related_assets"],
    }


def _asset_lookup(doc_id: str, asset: dict[str, str]) -> dict[str, Any]:
    asset_type = asset.get("type", "")
    asset_id = asset.get("asset_id", "")
    normalized_type = "figure" if asset_type == "image" else asset_type
    if normalized_type == "table":
        result = get_table(asset_id, doc_id=doc_id)
    elif normalized_type == "figure":
        result = get_image(asset_id, doc_id=doc_id)
    else:
        return {
            "status": "invalid",
            "asset_id": asset_id,
            "type": asset_type,
            "reason": "related asset type must be table, figure, or image",
        }
    if "error" in result:
        return {
            "status": "invalid",
            "asset_id": asset_id,
            "type": asset_type,
            "reason": result["error"],
        }
    return {"status": "accepted", "asset_id": asset_id, "type": asset_type}


def _verify_related_assets(doc_id: str, assets: list[dict[str, str]]) -> list[dict[str, Any]]:
    invalid: list[dict[str, Any]] = []
    for asset in assets:
        result = _asset_lookup(doc_id, asset)
        if result.get("status") != "accepted":
            invalid.append(result)
    return invalid


def materialize_unit_discovery(
    *,
    doc_id: str,
    discovery_md: str,
    unit_candidates: list[dict[str, Any]],
    output_dir: str | Path,
) -> dict[str, Any]:
    """Write discovery artifacts after structural evidence verification.

    Semantic unit selection is owned by the LLM/user proposal.  This function
    only checks that raw evidence refs and declared related assets are real and
    locatable in SpecIndex outputs.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "discovery.md").write_text(discovery_md, encoding="utf-8")

    accepted_units: list[dict[str, Any]] = []
    unresolved_items: list[dict[str, Any]] = []
    invalid_items: list[dict[str, Any]] = []

    for index, raw_candidate in enumerate(unit_candidates, start=1):
        if not isinstance(raw_candidate, dict):
            continue
        candidate = _normalize_candidate(raw_candidate, index)

        if candidate["status"] == "unresolved":
            unresolved_items.append(
                _unresolved_item(candidate, str(candidate.get("reason") or "unresolved"))
            )
            continue

        if not candidate["evidence_refs"]:
            unresolved_items.append(_unresolved_item(candidate, "missing_raw_evidence"))
            continue

        verification = verify_evidence(
            doc_id=doc_id,
            claim=f'{candidate["title"]}\n{candidate["reason"]}',
            evidence_refs=candidate["evidence_refs"],
        )
        invalid_assets = _verify_related_assets(doc_id, candidate["related_assets"])
        if verification.get("status") != "accepted" or invalid_assets:
            invalid_items.append(
                {
                    "unit_id": candidate["unit_id"],
                    "title": candidate["title"],
                    "kind": candidate["kind"],
                    "evidence_refs": candidate["evidence_refs"],
                    "related_assets": candidate["related_assets"],
                    "invalid_refs": verification.get("invalid_refs", []),
                    "invalid_assets": invalid_assets,
                }
            )
            continue

        accepted_units.append(
            {
                "unit_id": candidate["unit_id"],
                "doc_id": doc_id,
                "title": candidate["title"],
                "kind": candidate["kind"],
                "reason": candidate["reason"],
                "evidence_refs": candidate["evidence_refs"],
                "related_assets": candidate["related_assets"],
            }
        )

    verify_report = {
        "doc_id": doc_id,
        "accepted_count": len(accepted_units),
        "unresolved_count": len(unresolved_items),
        "invalid_count": len(invalid_items),
        "accepted": [
            {
                "unit_id": unit["unit_id"],
                "evidence_refs": unit["evidence_refs"],
                "related_assets": unit["related_assets"],
            }
            for unit in accepted_units
        ],
        "unresolved": unresolved_items,
        "invalid": invalid_items,
    }

    _write_json(out / "discovered_units.json", {"doc_id": doc_id, "units": accepted_units})
    _write_json(out / "unresolved.json", {"items": unresolved_items})
    _write_json(out / "verify_report.json", verify_report)

    return {
        "output_dir": str(out),
        "accepted_count": len(accepted_units),
        "unresolved_count": len(unresolved_items),
        "invalid_count": len(invalid_items),
    }


def _load_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize SpecIndex unit discovery.")
    parser.add_argument("--input", required=True, help="JSON payload with doc_id and unit_candidates.")
    parser.add_argument("--out", required=True, help="Output directory for discovery artifacts.")
    args = parser.parse_args(argv)

    payload = _load_payload(Path(args.input))
    result = materialize_unit_discovery(
        doc_id=str(payload["doc_id"]),
        discovery_md=str(payload.get("discovery_md") or ""),
        unit_candidates=payload.get("unit_candidates") if isinstance(payload.get("unit_candidates"), list) else [],
        output_dir=args.out,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

