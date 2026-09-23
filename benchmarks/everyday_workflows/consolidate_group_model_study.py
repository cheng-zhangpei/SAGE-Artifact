"""Merge checkpoint/recovery runs and evaluate SAGE repair on every valid draft."""

import argparse
import json
from pathlib import Path

from sage.v2.guards import semantic_normalize
from sage.v2.scenario import build_scenario
from sage.v2.synthesis import direct_sage

from .composition_suite import build_case
from .consolidate_composition_study import candidate_json
from .dataset import load_workflows, scenario_spec
from .evaluate import evaluate_guards, parse_candidate
from .run_composition_suite import evaluate as evaluate_composition


def read_checkpoint(path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["manifest"], payload["records"]


def select(paths):
    selected = {}
    attempts = {}
    manifests = []
    for path in paths:
        manifest, rows = read_checkpoint(path)
        manifests.append({"path": str(path), "manifest": manifest})
        for row in rows:
            identity = row["workflow"]
            attempts.setdefault(identity, []).append({
                "source": str(path), "transport_status": row["transport_status"],
                "error": row.get("error"), "status_code": row.get("status_code"),
            })
            if identity not in selected or row["transport_status"] == "OK":
                selected[identity] = {"source": str(path), "row": row}
    return selected, attempts, manifests


def base_counts(evaluation):
    probes = evaluation["probes"]
    dangerous = [probe for probe in probes if probe["class"] == "danger"]
    benign = [probe for probe in probes if probe["class"] == "benign"]
    return {
        "verification_status": evaluation["verification_status"],
        "dangerous_probes": len(dangerous), "benign_probes": len(benign),
        "missed": sum(probe["decision"] == "ALLOW" for probe in dangerous),
        "blocked": sum(probe["decision"] == "DENY" for probe in benign),
    }


def composition_counts(evaluation):
    return {key: evaluation[key] for key in (
        "verification_status", "dangerous_probes", "benign_probes", "missed", "blocked")}


def aggregate(records, key):
    values = [record[key] for record in records]
    dangerous = sum(value["dangerous_probes"] for value in values)
    benign = sum(value["benign_probes"] for value in values)
    missed = sum(value["missed"] for value in values)
    blocked = sum(value["blocked"] for value in values)
    return {
        "evaluated": len(values),
        "pass": sum(value["verification_status"] == "PASS" for value in values),
        "fail": sum(value["verification_status"] == "FAIL" for value in values),
        "unknown": sum(value["verification_status"] == "UNKNOWN" for value in values),
        "dangerous": dangerous, "benign": benign, "missed": missed, "blocked": blocked,
        "der_percent": 100 * (dangerous - missed) / dangerous if dangerous else 0,
        "bbr_percent": 100 * blocked / benign if benign else 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--easy", action="append", type=Path, default=[])
    parser.add_argument("--composition", action="append", type=Path, default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)

    easy, easy_attempts, easy_manifests = select(args.easy)
    composition, composition_attempts, composition_manifests = select(args.composition)
    workflows = {workflow["id"]: workflow for workflow in load_workflows()}
    records = []
    missing = []

    for identity in sorted(easy):
        item = easy[identity]
        row = item["row"]
        if row["transport_status"] != "OK":
            missing.append(identity)
            continue
        workflow = workflows[identity]
        candidate = parse_candidate(workflow, row["raw_content"])
        scenario = build_scenario(scenario_spec(workflow))
        direct = direct_sage(scenario.model, scenario.policy)
        additive = semantic_normalize([*candidate, *direct])
        records.append({
            "workflow": identity, "layer": "base", "source": item["source"],
            "initial": base_counts(row["evaluation"]),
            "additive_repair": base_counts(evaluate_guards(workflow, additive, 5000)),
            "direct_sage": base_counts(evaluate_guards(workflow, direct, 5000)),
        })

    for identity in sorted(composition):
        item = composition[identity]
        row = item["row"]
        if row["transport_status"] != "OK":
            missing.append(identity)
            continue
        case = build_case(row["family"], int(row["count"]))
        candidate = parse_candidate(case, row["raw_content"])
        scenario = build_scenario(case["spec"])
        direct = direct_sage(scenario.model, scenario.policy)
        additive = semantic_normalize([*candidate, *direct])
        records.append({
            "workflow": identity, "layer": "composition", "source": item["source"],
            "initial": composition_counts(row["evaluation"]),
            "additive_repair": composition_counts(
                evaluate_composition(case, candidate_json(additive), 5000)),
            "direct_sage": composition_counts(
                evaluate_composition(case, candidate_json(direct), 5000)),
        })

    layers = {}
    for layer in ("base", "composition", "all"):
        subset = records if layer == "all" else [record for record in records if record["layer"] == layer]
        layers[layer] = {key: aggregate(subset, key)
                         for key in ("initial", "additive_repair", "direct_sage")}
    payload = {
        "status": "COMPLETE" if not missing else "INCOMPLETE_TRANSPORT",
        "expected_tasks": 72, "evaluated_tasks": len(records), "missing": sorted(missing),
        "layers": layers, "records": records,
        "transport_attempts": {**easy_attempts, **composition_attempts},
        "manifests": [*easy_manifests, *composition_manifests],
    }
    (args.output_dir / "results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Group-model 72-task authoring study", "",
        f"Status: **{payload['status']}**; evaluated: **{len(records)}/72**.", "",
        "| Layer / arm | Evaluated | PASS | FAIL | UNKNOWN | DER | BBR |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    labels = (("initial", "one-shot draft"), ("additive_repair", "SAGE additive"),
              ("direct_sage", "DirectSAGE"))
    for layer in ("base", "composition", "all"):
        for key, label in labels:
            value = layers[layer][key]
            lines.append(
                f"| {layer}: {label} | {value['evaluated']} | {value['pass']} | {value['fail']} | "
                f"{value['unknown']} | {value['der_percent']:.1f}% | {value['bbr_percent']:.1f}% |")
    lines += ["", "Missing after recorded transport recovery: " +
              (", ".join(f"`{identity}`" for identity in sorted(missing)) if missing else "none") + ".", ""]
    (args.output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "missing": payload["missing"],
                      "all": layers["all"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
