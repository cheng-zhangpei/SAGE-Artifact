"""Freeze stratified audit samples outside the narrow candidate population."""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def slim(row: dict, stratum: str) -> dict:
    return {
        "id": row["id"], "name": row["name"], "author": row.get("author"),
        "source_sha256": row["source_sha256"], "structure_fingerprint": row["structure_fingerprint"],
        "node_count": row["node_count"], "main_ai_nodes": row["main_ai_nodes"],
        "external_action_candidates": row["external_action_candidates"],
        "binary_sink_candidates": row["binary_sink_candidates"],
        "explicit_file_sources": row["explicit_file_sources"], "stratum": stratum,
        "review_status": "pending_blinded_dependency_review",
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--inventory", type=Path, required=True)
    p.add_argument("--candidate-manifest", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--seed", type=int, default=20260909)
    p.add_argument("--per-stratum", type=int, default=50)
    args = p.parse_args()
    rows = json.loads(args.inventory.read_text(encoding="utf-8"))
    candidate_ids = {c["id"] for c in json.loads(args.candidate_manifest.read_text(encoding="utf-8"))["candidates"]}
    binary_negative = [r for r in rows if r["llm_related"] and r["binary_sink_candidates"] and r["id"] not in candidate_ids]
    nonbinary_action = [r for r in rows if r["llm_related"] and r["external_action_candidates"] and not r["binary_sink_candidates"]]
    rng = random.Random(args.seed)
    a = rng.sample(sorted(binary_negative, key=lambda r: r["id"]), min(args.per_stratum, len(binary_negative)))
    b = rng.sample(sorted(nonbinary_action, key=lambda r: r["id"]), min(args.per_stratum, len(nonbinary_action)))
    output = {
        "schema_version": 1, "seed": args.seed,
        "purpose": "estimate detector misses, not collision prevalence in the full catalog",
        "population_sizes": {"binary_sink_outside_narrow_detector": len(binary_negative), "nonbinary_external_action": len(nonbinary_action)},
        "sample_sizes": {"binary_sink_outside_narrow_detector": len(a), "nonbinary_external_action": len(b)},
        "samples": [*(slim(x, "binary_sink_outside_narrow_detector") for x in a), *(slim(x, "nonbinary_external_action") for x in b)],
    }
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"population_sizes": output["population_sizes"], "sample_sizes": output["sample_sizes"], "seed": args.seed}))


if __name__ == "__main__":
    main()
