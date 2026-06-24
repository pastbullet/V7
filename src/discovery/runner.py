"""Run the SpecIndex unit discovery agent and materialize discovered units."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from src.agent.loop import agentic_rag, load_system_prompt
from src.reading.runner import extract_json_payload
from src.discovery.units import materialize_unit_discovery


def _build_discovery_query(discovery_goal: str) -> str:
    return (
        "Discover protocol units relevant to this goal without assuming the unit names in advance:\n"
        f"{discovery_goal}\n\n"
        "Follow the SpecIndex flow, inspect structure before pages/assets, and return only the JSON payload."
    )


async def run_unit_discovery_agent(
    *,
    doc_name: str,
    discovery_goal: str,
    output_dir: str | Path,
    model: str | None = None,
    max_turns: int = 25,
) -> dict[str, Any]:
    """Run tool-using discovery and write auditable unit artifacts."""
    system_prompt = load_system_prompt("unit_discovery_system.txt")
    response = await agentic_rag(
        query=_build_discovery_query(discovery_goal),
        doc_name=doc_name,
        model=model,
        max_turns=max_turns,
        prompt_file="unit_discovery_system.txt",
        system_prompt_override=system_prompt,
    )
    payload = extract_json_payload(response.answer)
    payload.setdefault("doc_id", doc_name)
    payload.setdefault("discovery_md", "")
    if not isinstance(payload.get("unit_candidates"), list):
        payload["unit_candidates"] = []

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "llm_payload.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    result = materialize_unit_discovery(
        doc_id=str(payload["doc_id"]),
        discovery_md=str(payload.get("discovery_md") or ""),
        unit_candidates=payload["unit_candidates"],
        output_dir=out,
    )
    result["llm_turns"] = response.total_turns
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run SpecIndex unit discovery agent.")
    parser.add_argument("--doc", required=True, help="Document name or SpecIndex doc id.")
    parser.add_argument("--goal", required=True, help="Discovery goal.")
    parser.add_argument("--out", required=True, help="Output directory for discovery artifacts.")
    parser.add_argument("--model", default=None, help="Optional LLM model name.")
    parser.add_argument("--max-turns", type=int, default=25)
    args = parser.parse_args(argv)

    result = asyncio.run(
        run_unit_discovery_agent(
            doc_name=args.doc,
            discovery_goal=args.goal,
            output_dir=args.out,
            model=args.model,
            max_turns=args.max_turns,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

