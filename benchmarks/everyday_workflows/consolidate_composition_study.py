"""Freeze selected composition candidates and compute SAGE repair/synthesis outcomes."""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from sage.v2.guards import semantic_normalize
from sage.v2.scenario import build_scenario
from sage.v2.synthesis import direct_sage

from .composition_suite import COUNTS, FAMILIES, build_case
from .evaluate import parse_candidate
from .run_composition_suite import evaluate


def read(path):
    if path.name == "checkpoint.json":
        return json.loads(path.read_text(encoding="utf-8"))["records"]
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("workflow"):
            rows.append(row)
    return rows


def rate(numerator, denominator):
    return 100.0 * numerator / denominator if denominator else 0.0


def metrics(rows, key):
    evaluations = [row[key] for row in rows]
    dangerous = sum(e["dangerous_probes"] for e in evaluations)
    benign = sum(e["benign_probes"] for e in evaluations)
    missed = sum(e["missed"] for e in evaluations)
    blocked = sum(e["blocked"] for e in evaluations)
    return {
        "pass": sum(e["verification_status"] == "PASS" for e in evaluations),
        "fail": sum(e["verification_status"] == "FAIL" for e in evaluations),
        "unknown": sum(e["verification_status"] == "UNKNOWN" for e in evaluations),
        "dangerous": dangerous, "benign": benign, "missed": missed, "blocked": blocked,
        "der_percent": rate(dangerous - missed, dangerous),
        "bbr_percent": rate(blocked, benign),
    }


def candidate_json(constraints):
    clauses = []
    for constraint in constraints:
        if constraint.param_filter.match_all or constraint.param_filter.wildcard_patterns:
            raise ValueError("Composition candidates require exact parameter patterns")
        for pattern in constraint.param_filter.exact_patterns:
            clauses.append({
                "agent": constraint.agent,
                "tool": constraint.tool,
                "params": dict(pattern),
                "forbidden_labels": sorted(constraint.forbidden_labels),
            })
    return json.dumps({"guards": clauses}, ensure_ascii=False, separators=(",", ":"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", action="append", type=Path, required=True)
    parser.add_argument("--recovery", type=Path, required=True)
    parser.add_argument("--normalized", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)

    selected = {}
    sources = {}
    for path in args.base:
        for row in read(path):
            selected[row["workflow"]] = row
            sources[row["workflow"]] = str(path)
    for row in read(args.recovery):
        if row["evaluation"].get("candidate_status") == "VALID":
            selected[row["workflow"]] = row
            sources[row["workflow"]] = str(args.recovery)
    for row in read(args.normalized):
        selected[row["workflow"]] = row
        sources[row["workflow"]] = str(args.normalized)

    expected = {build_case(family, count)["id"] for family in FAMILIES for count in COUNTS}
    if set(selected) != expected:
        raise ValueError(f"Selection mismatch: missing={sorted(expected-set(selected))}, extra={sorted(set(selected)-expected)}")

    frozen = []
    for workflow in sorted(expected):
        row = selected[workflow]
        family, count = row["family"], int(row["count"])
        case = build_case(family, count)
        guards = parse_candidate(case, row["raw_content"])
        initial = evaluate(case, row["raw_content"], 5000)
        scenario = build_scenario(case["spec"])
        direct = direct_sage(scenario.model, scenario.policy)
        additive = semantic_normalize([*guards, *direct])
        additive_raw = candidate_json(additive)
        direct_raw = candidate_json(direct)
        additive_evaluation = evaluate(case, additive_raw, 5000)
        direct_evaluation = evaluate(case, direct_raw, 5000)
        frozen.append({
            "workflow": workflow, "family": family, "count": count,
            "source": sources[workflow], "initial": initial,
            "additive_repair": additive_evaluation, "direct_sage": direct_evaluation,
            "initial_raw_content": row["raw_content"],
            "additive_raw_content": additive_raw, "direct_raw_content": direct_raw,
        })

    summary = {
        "tasks": len(frozen),
        "initial": metrics(frozen, "initial"),
        "additive_repair": metrics(frozen, "additive_repair"),
        "direct_sage": metrics(frozen, "direct_sage"),
        "by_count": {}, "by_family": {},
    }
    for count in COUNTS:
        group = [row for row in frozen if row["count"] == count]
        summary["by_count"][str(count)] = metrics(group, "initial")
    for family in FAMILIES:
        group = [row for row in frozen if row["family"] == family]
        summary["by_family"][family] = metrics(group, "initial")

    (args.output_dir / "selected_results.json").write_text(
        json.dumps({"summary": summary, "records": frozen}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Composition benchmark: frozen MiMo-v2.5 results", "",
        f"Tasks: **{len(frozen)}** (six business-family clusters x six nested sizes).", "",
        "| Arm | PASS | FAIL | UNKNOWN | DER | BBR |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, key in (("MiMo one-shot", "initial"), ("SAGE additive repair", "additive_repair"),
                       ("DirectSAGE", "direct_sage")):
        item = summary[key]
        lines.append(f"| {label} | {item['pass']}/36 | {item['fail']}/36 | {item['unknown']}/36 | "
                     f"{item['der_percent']:.1f}% | {item['bbr_percent']:.1f}% |")
    lines += ["", "## Initial candidates by dispatch count", "",
              "| Dispatches | PASS | FAIL | UNKNOWN | DER | BBR |",
              "|---:|---:|---:|---:|---:|---:|"]
    for count in COUNTS:
        item = summary["by_count"][str(count)]
        lines.append(f"| {count} | {item['pass']}/6 | {item['fail']}/6 | {item['unknown']}/6 | "
                     f"{item['der_percent']:.1f}% | {item['bbr_percent']:.1f}% |")
    lines += ["", "Levels within each family are nested and correlated; treat size trends as descriptive.", ""]
    (args.output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
