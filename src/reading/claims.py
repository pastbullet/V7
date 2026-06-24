"""Materialize LLM-proposed readings and claims into auditable artifacts."""

from __future__ import annotations

import json
import argparse
from pathlib import Path
from typing import Any

from src.tools.specindex_assets import verify_evidence


CANONICAL_CLAIM_KINDS = {
    "field_presence",
    "field_width",
    "offset",
    "condition",
    "transition",
    "response_branch",
    "completion_condition",
    "other",
}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    path.write_text(text + ("\n" if text else ""), encoding="utf-8")


def _normalize_candidate(raw: dict[str, Any], index: int) -> dict[str, Any]:
    claim_id = str(raw.get("claim_id") or f"claim_{index:04d}")
    text = str(raw.get("text") or raw.get("claim") or "").strip()
    return {
        **raw,
        "claim_id": claim_id,
        "text": text,
        "kind": str(raw.get("kind") or "unspecified"),
        "status": str(raw.get("status") or "accepted"),
        "evidence_refs": raw.get("evidence_refs") if isinstance(raw.get("evidence_refs"), list) else [],
    }


def _unresolved_item(candidate: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "claim_id": candidate["claim_id"],
        "text": candidate["text"],
        "kind": candidate["kind"],
        "reason": reason,
        "evidence_refs": candidate["evidence_refs"],
    }


def materialize_reading_claims(
    *,
    doc_id: str,
    unit_id: str,
    reading_md: str,
    claim_candidates: list[dict[str, Any]],
    output_dir: str | Path,
) -> dict[str, Any]:
    """Write reading.md, accepted claims, unresolved items, and evidence report.

    The semantic proposal is assumed to come from an LLM or user. This function
    only enforces structural evidence discipline through ``verify_evidence``.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "reading.md").write_text(reading_md, encoding="utf-8")

    accepted_claims: list[dict[str, Any]] = []
    unresolved_items: list[dict[str, Any]] = []
    invalid_items: list[dict[str, Any]] = []
    schema_warnings: list[dict[str, Any]] = []
    evidence_map: dict[str, list[dict[str, Any]]] = {}

    for index, raw_candidate in enumerate(claim_candidates, start=1):
        if not isinstance(raw_candidate, dict):
            continue
        candidate = _normalize_candidate(raw_candidate, index)
        if candidate["kind"] not in CANONICAL_CLAIM_KINDS:
            schema_warnings.append(
                {
                    "claim_id": candidate["claim_id"],
                    "field": "kind",
                    "value": candidate["kind"],
                    "reason": "non_canonical_claim_kind",
                    "allowed": sorted(CANONICAL_CLAIM_KINDS),
                }
            )

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
            claim=candidate["text"],
            evidence_refs=candidate["evidence_refs"],
        )
        if verification.get("status") != "accepted":
            invalid_items.append(
                {
                    "claim_id": candidate["claim_id"],
                    "text": candidate["text"],
                    "kind": candidate["kind"],
                    "evidence_refs": candidate["evidence_refs"],
                    "invalid_refs": verification.get("invalid_refs", []),
                }
            )
            continue

        accepted = {
            "claim_id": candidate["claim_id"],
            "unit_id": unit_id,
            "doc_id": doc_id,
            "text": candidate["text"],
            "kind": candidate["kind"],
            "evidence_refs": candidate["evidence_refs"],
        }
        accepted_claims.append(accepted)
        evidence_map[candidate["claim_id"]] = candidate["evidence_refs"]

    verify_report = {
        "doc_id": doc_id,
        "unit_id": unit_id,
        "accepted_count": len(accepted_claims),
        "unresolved_count": len(unresolved_items),
        "invalid_count": len(invalid_items),
        "accepted": [
            {"claim_id": claim["claim_id"], "evidence_refs": claim["evidence_refs"]}
            for claim in accepted_claims
        ],
        "unresolved": unresolved_items,
        "invalid": invalid_items,
        "schema_warnings": schema_warnings,
    }

    _write_jsonl(out / "claims.jsonl", accepted_claims)
    _write_json(out / "evidence_map.json", evidence_map)
    _write_json(out / "unresolved.json", {"items": unresolved_items})
    _write_json(out / "verify_report.json", verify_report)

    return {
        "output_dir": str(out),
        "accepted_count": len(accepted_claims),
        "unresolved_count": len(unresolved_items),
        "invalid_count": len(invalid_items),
    }


def _load_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize SpecIndex reading claims.")
    parser.add_argument("--input", required=True, help="JSON payload with doc_id, unit_id, reading_md, claim_candidates.")
    parser.add_argument("--out", required=True, help="Output directory for reading.md, claims.jsonl, evidence_map.json, unresolved.json, verify_report.json.")
    args = parser.parse_args(argv)

    payload = _load_payload(Path(args.input))
    result = materialize_reading_claims(
        doc_id=str(payload["doc_id"]),
        unit_id=str(payload["unit_id"]),
        reading_md=str(payload.get("reading_md") or ""),
        claim_candidates=payload.get("claim_candidates") if isinstance(payload.get("claim_candidates"), list) else [],
        output_dir=args.out,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
