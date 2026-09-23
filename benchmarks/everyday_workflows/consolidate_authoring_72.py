"""Combine the 36 base and 36 composition workflows into the frozen 72-task study."""

import argparse
import json
from pathlib import Path

from sage.v2.guards import semantic_normalize
from sage.v2.scenario import build_scenario
from sage.v2.synthesis import direct_sage

from .consolidate_composition_study import candidate_json
from .dataset import load_workflows, scenario_spec
from .evaluate import evaluate_guards, parse_candidate


def probe_counts(evaluation):
    probes = evaluation["probes"]
    dangerous = [p for p in probes if p["class"] == "danger"]
    benign = [p for p in probes if p["class"] == "benign"]
    return {
        "verification_status": evaluation["verification_status"],
        "dangerous_probes": len(dangerous), "benign_probes": len(benign),
        "missed": sum(p["decision"] == "ALLOW" for p in dangerous),
        "blocked": sum(p["decision"] == "DENY" for p in benign),
    }


def aggregate(records, key):
    values = [row[key] for row in records]
    dangerous = sum(v["dangerous_probes"] for v in values)
    benign = sum(v["benign_probes"] for v in values)
    missed = sum(v["missed"] for v in values)
    blocked = sum(v["blocked"] for v in values)
    return {
        "pass": sum(v["verification_status"] == "PASS" for v in values),
        "fail": sum(v["verification_status"] == "FAIL" for v in values),
        "unknown": sum(v["verification_status"] == "UNKNOWN" for v in values),
        "dangerous": dangerous, "benign": benign, "missed": missed, "blocked": blocked,
        "der_percent": 100 * (dangerous - missed) / dangerous,
        "bbr_percent": 100 * blocked / benign,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--easy", type=Path, required=True)
    parser.add_argument("--composition", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)

    workflows = {w["id"]: w for w in load_workflows()}
    easy_rows = [json.loads(line) for line in args.easy.read_text(encoding="utf-8").splitlines()]
    records = []
    for row in easy_rows:
        workflow = workflows[row["workflow"]]
        guards = parse_candidate(workflow, row["raw_content"])
        scenario = build_scenario(scenario_spec(workflow))
        direct = direct_sage(scenario.model, scenario.policy)
        additive = semantic_normalize([*guards, *direct])
        records.append({
            "workflow": row["workflow"], "layer": "base",
            "initial": probe_counts(row["evaluation"]),
            "additive_repair": probe_counts(evaluate_guards(workflow, additive, 5000)),
            "direct_sage": probe_counts(evaluate_guards(workflow, direct, 5000)),
        })

    composition = json.loads(args.composition.read_text(encoding="utf-8"))
    for row in composition["records"]:
        records.append({
            "workflow": row["workflow"], "layer": "composition",
            "initial": row["initial"], "additive_repair": row["additive_repair"],
            "direct_sage": row["direct_sage"],
        })
    if len(records) != 72:
        raise ValueError(f"Expected 72 tasks, got {len(records)}")

    layers = {}
    for layer in ("base", "composition", "all"):
        subset = records if layer == "all" else [r for r in records if r["layer"] == layer]
        layers[layer] = {key: aggregate(subset, key)
                         for key in ("initial", "additive_repair", "direct_sage")}
    payload = {"tasks": 72, "layers": layers, "records": records}
    (args.output_dir / "results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Frozen 72-workflow guard-authoring study", "",
        "The suite contains 36 base workflows and 36 nested composition workflows.", "",
        "| Layer / arm | PASS | FAIL | UNKNOWN | DER | BBR |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for layer, denominator in (("base", 36), ("composition", 36), ("all", 72)):
        for label, key in (("MiMo one-shot", "initial"), ("SAGE additive", "additive_repair"),
                           ("DirectSAGE", "direct_sage")):
            value = layers[layer][key]
            lines.append(f"| {layer}: {label} | {value['pass']}/{denominator} | "
                         f"{value['fail']}/{denominator} | {value['unknown']}/{denominator} | "
                         f"{value['der_percent']:.1f}% | {value['bbr_percent']:.1f}% |")
    lines += ["", "Composition levels within a business family are nested and correlated.", ""]
    (args.output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(layers["all"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
