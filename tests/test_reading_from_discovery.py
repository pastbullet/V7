from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_run_readings_from_discovery_calls_reader_once_per_discovered_unit(
    tmp_path: Path,
    monkeypatch,
):
    discovery_path = tmp_path / "discoveries" / "discovered_units.json"
    _write_json(
        discovery_path,
        {
            "doc_id": "demo_doc",
            "units": [
                {
                    "unit_id": "flogi_payload",
                    "title": "FLOGI/PLOGI/LS_ACC payload structure",
                    "kind": "message_structure",
                    "reason": "Table caption and cells identify the payload structure.",
                    "evidence_refs": [
                        {
                            "type": "text_span",
                            "span_id": "p166_s0003",
                            "quote": "Table 149",
                        }
                    ],
                    "related_assets": [{"type": "table", "asset_id": "table_0157"}],
                },
                {
                    "unit_id": "flogi_flow",
                    "title": "FLOGI request and response flow",
                    "kind": "procedure",
                    "reason": "The section describes request and response branches.",
                    "evidence_refs": [],
                    "related_assets": [],
                },
            ],
        },
    )

    from src.reading import from_discovery

    calls: list[dict] = []

    async def fake_run_reading_claim_agent(**kwargs):
        calls.append(kwargs)
        out = Path(kwargs["output_dir"])
        out.mkdir(parents=True, exist_ok=True)
        _write_json(
            out / "verify_report.json",
            {
                "accepted_count": 1,
                "unresolved_count": 0,
                "invalid_count": 0,
            },
        )
        return {
            "output_dir": str(out),
            "accepted_count": 1,
            "unresolved_count": 0,
            "invalid_count": 0,
            "llm_turns": 3,
        }

    monkeypatch.setattr(from_discovery, "run_reading_claim_agent", fake_run_reading_claim_agent)

    output_dir = tmp_path / "readings_from_discovery"
    result = asyncio.run(
        from_discovery.run_readings_from_discovery(
            discovery_path=discovery_path,
            output_dir=output_dir,
            model="fake-reading-model",
        )
    )

    assert result["unit_count"] == 2
    assert result["accepted_claim_count"] == 2
    assert [call["doc_name"] for call in calls] == ["demo_doc", "demo_doc"]
    assert [call["unit_id"] for call in calls] == ["flogi_payload", "flogi_flow"]
    assert calls[0]["model"] == "fake-reading-model"
    assert calls[0]["output_dir"] == output_dir / "flogi_payload"
    assert "FLOGI/PLOGI/LS_ACC payload structure" in calls[0]["reading_goal"]
    assert "table_0157" in calls[0]["reading_goal"]
    assert "p166_s0003" in calls[0]["reading_goal"]
    assert "Search for" not in calls[0]["reading_goal"]

    manifest = json.loads((output_dir / "reading_manifest.json").read_text(encoding="utf-8"))
    assert manifest["doc_id"] == "demo_doc"
    assert [unit["unit_id"] for unit in manifest["units"]] == ["flogi_payload", "flogi_flow"]
    assert manifest["totals"]["accepted_claim_count"] == 2


def test_readings_from_discovery_cli_help():
    repo_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.reading.from_discovery",
            "--help",
        ],
        cwd=repo_root,
        env={"PYTHONPATH": str(repo_root)},
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "--discovery" in completed.stdout
    assert "--model" in completed.stdout
