"""Run the SpecIndex reading agent and materialize its claim payload."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path
from typing import Any

from src.agent.loop import agentic_rag, load_system_prompt
from src.reading.claims import materialize_reading_claims


def extract_json_payload(text: str) -> dict[str, Any]:
    """Extract a JSON object from a raw LLM answer."""
    raw = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL | re.IGNORECASE)
    if fenced:
        raw = fenced.group(1).strip()
    else:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end >= start:
            raw = raw[start : end + 1]
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("LLM reading payload must be a JSON object")
    return payload


def _build_reading_query(unit_id: str, reading_goal: str) -> str:
    return (
        f"Read the specification unit `{unit_id}` for this goal:\n"
        f"{reading_goal}\n\n"
        "Follow the SpecIndex flow, verify raw evidence refs, and return only the JSON payload."
    )


async def run_reading_claim_agent(
    *,
    doc_name: str,
    unit_id: str,
    reading_goal: str,
    output_dir: str | Path,
    model: str | None = None,
    max_turns: int = 25,
) -> dict[str, Any]:
    """Run the tool-using reader and write auditable reading artifacts."""
    system_prompt = load_system_prompt("reading_claim_system.txt")
    response = await agentic_rag(
        query=_build_reading_query(unit_id, reading_goal),
        doc_name=doc_name,
        model=model,
        max_turns=max_turns,
        prompt_file="reading_claim_system.txt",
        system_prompt_override=system_prompt,
    )
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    try:
        payload = extract_json_payload(response.answer)
    except Exception as exc:  # noqa: BLE001
        (out / "raw_answer.txt").write_text(response.answer or "", encoding="utf-8")
        (out / "runner_error.json").write_text(
            json.dumps(
                {
                    "error": str(exc),
                    "doc_id": doc_name,
                    "unit_id": unit_id,
                    "llm_turns": response.total_turns,
                    "pages_retrieved": response.pages_retrieved,
                    "all_pages_requested": response.all_pages_requested,
                    "trace": [item.model_dump() for item in response.trace],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        raise

    payload.setdefault("doc_id", doc_name)
    payload.setdefault("unit_id", unit_id)
    payload.setdefault("reading_md", "")
    if not isinstance(payload.get("claim_candidates"), list):
        payload["claim_candidates"] = []

    (out / "llm_payload.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    result = materialize_reading_claims(
        doc_id=str(payload["doc_id"]),
        unit_id=str(payload["unit_id"]),
        reading_md=str(payload.get("reading_md") or ""),
        claim_candidates=payload["claim_candidates"],
        output_dir=out,
    )
    result["llm_turns"] = response.total_turns
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run SpecIndex reading agent and materialize claims.")
    parser.add_argument("--doc", required=True, help="Document name or SpecIndex doc id.")
    parser.add_argument("--unit-id", required=True, help="Short unit id for output claims.")
    parser.add_argument("--goal", required=True, help="Reading goal for this unit.")
    parser.add_argument("--out", required=True, help="Output directory for reading artifacts.")
    parser.add_argument("--model", default=None, help="Optional LLM model name.")
    parser.add_argument("--max-turns", type=int, default=25)
    args = parser.parse_args(argv)

    result = asyncio.run(
        run_reading_claim_agent(
            doc_name=args.doc,
            unit_id=args.unit_id,
            reading_goal=args.goal,
            output_dir=args.out,
            model=args.model,
            max_turns=args.max_turns,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
