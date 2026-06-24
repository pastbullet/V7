"""Bundle verified reading claims into a single IR-facing input."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.tools.specindex_assets import verify_evidence


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_json_if_exists(path: Path) -> Any | None:
    if not path.exists():
        return None
    return _read_json(path)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        item = json.loads(text)
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    path.write_text(text + ("\n" if text else ""), encoding="utf-8")


def _invalid_claim(claim: dict[str, Any], source: Path, reason: str, invalid_refs: list[Any] | None = None) -> dict[str, Any]:
    return {
        "claim_id": str(claim.get("claim_id") or ""),
        "unit_id": claim.get("unit_id"),
        "doc_id": claim.get("doc_id"),
        "text": str(claim.get("text") or ""),
        "kind": str(claim.get("kind") or "unspecified"),
        "source_reading": str(source),
        "reason": reason,
        "invalid_refs": invalid_refs or [],
    }


def _load_unresolved(reading_dir: Path) -> list[dict[str, Any]]:
    payload = _read_json_if_exists(reading_dir / "unresolved.json")
    if not isinstance(payload, dict):
        return []
    items = payload.get("items")
    if not isinstance(items, list):
        return []
    unresolved: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            unresolved.append({**item, "source_reading": str(reading_dir)})
    return unresolved


def build_claim_bundle(
    *,
    reading_dirs: list[str | Path],
    output_dir: str | Path,
    doc_id: str | None = None,
) -> dict[str, Any]:
    """Merge accepted reading claims and re-run structural evidence checks.

    This function is deliberately mechanical: it does not infer protocol
    semantics and it does not read ``reading.md``.  Claims enter the bundle only
    when their raw evidence refs still pass ``verify_evidence``.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    accepted: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    evidence_map: dict[str, list[dict[str, Any]]] = {}
    seen_claim_ids: set[str] = set()
    sources = [Path(path) for path in reading_dirs]

    for reading_dir in sources:
        unresolved.extend(_load_unresolved(reading_dir))
        for raw_claim in _read_jsonl(reading_dir / "claims.jsonl"):
            claim_id = str(raw_claim.get("claim_id") or "")
            source_doc_id = str(raw_claim.get("doc_id") or "")
            verification_doc_id = str(doc_id or source_doc_id)
            text = str(raw_claim.get("text") or "")
            evidence_refs = raw_claim.get("evidence_refs")
            if not claim_id:
                invalid.append(_invalid_claim(raw_claim, reading_dir, "missing_claim_id"))
                continue
            if claim_id in seen_claim_ids:
                invalid.append(_invalid_claim(raw_claim, reading_dir, "duplicate_claim_id"))
                continue
            if not verification_doc_id:
                invalid.append(_invalid_claim(raw_claim, reading_dir, "missing_doc_id"))
                continue
            if not isinstance(evidence_refs, list) or not evidence_refs:
                invalid.append(_invalid_claim(raw_claim, reading_dir, "missing_raw_evidence"))
                continue

            verification = verify_evidence(
                doc_id=verification_doc_id,
                claim=text,
                evidence_refs=evidence_refs,
            )
            if verification.get("status") != "accepted":
                invalid.append(
                    _invalid_claim(
                        raw_claim,
                        reading_dir,
                        "evidence_verification_failed",
                        verification.get("invalid_refs", []),
                    )
                )
                continue

            bundled = {
                **raw_claim,
                "claim_id": claim_id,
                "doc_id": verification_doc_id,
                "source_doc_id": source_doc_id or verification_doc_id,
                "text": text,
                "kind": str(raw_claim.get("kind") or "unspecified"),
                "evidence_refs": evidence_refs,
                "source_reading": str(reading_dir),
            }
            accepted.append(bundled)
            seen_claim_ids.add(claim_id)
            evidence_map[claim_id] = evidence_refs

    verify_report = {
        "source_readings": [str(source) for source in sources],
        "doc_id": doc_id,
        "accepted_count": len(accepted),
        "unresolved_count": len(unresolved),
        "invalid_count": len(invalid),
        "accepted": [
            {
                "claim_id": claim["claim_id"],
                "unit_id": claim.get("unit_id"),
                "doc_id": claim["doc_id"],
                "source_reading": claim["source_reading"],
                "evidence_refs": claim["evidence_refs"],
            }
            for claim in accepted
        ],
        "unresolved": unresolved,
        "invalid": invalid,
    }

    _write_jsonl(out / "claims_bundle.jsonl", accepted)
    _write_json(out / "evidence_map.json", evidence_map)
    _write_json(out / "unresolved.json", {"items": unresolved})
    _write_json(out / "verify_report.json", verify_report)

    return {
        "output_dir": str(out),
        "accepted_count": len(accepted),
        "unresolved_count": len(unresolved),
        "invalid_count": len(invalid),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bundle verified SpecIndex reading claims.")
    parser.add_argument(
        "--reading",
        action="append",
        required=True,
        help="Reading output directory containing claims.jsonl. Repeat for multiple readings.",
    )
    parser.add_argument("--out", required=True, help="Output directory for bundled claims.")
    parser.add_argument(
        "--doc-id",
        default=None,
        help="Optional canonical document id to use for evidence verification and bundled claims.",
    )
    args = parser.parse_args(argv)

    result = build_claim_bundle(
        reading_dirs=[Path(path) for path in args.reading],
        output_dir=Path(args.out),
        doc_id=args.doc_id,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
