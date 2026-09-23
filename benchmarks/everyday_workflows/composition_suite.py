"""Six-family, six-level composition suite bridging W01-W36 and Dense."""

import argparse
import hashlib
import json
from pathlib import Path

from sage.v2.scenario import build_scenario
from sage.v2.synthesis import direct_sage

from .business_families import BUILDERS, assess as assess_family, build_family
from .dense import assess as assess_dense, build_count
from .run import fingerprint


COUNTS = (8, 16, 24, 32, 40, 48)
FAMILIES = ("support_finance", *BUILDERS)
ROOT = Path(__file__).resolve().parent


def build_case(family, count):
    if family == "support_finance":
        case = build_count(count)
        case["id"] = f"COMP-SUP-{count:02d}"
        case["family"] = family
        case["dataset_role"] = "composition-benchmark"
        return case
    case = build_family(family, count)
    case["id"] = f"COMP-{family.upper().replace('_', '-')}-{count:02d}"
    case["dataset_role"] = "composition-benchmark"
    return case


def build_suite():
    return [build_case(family, count) for family in FAMILIES for count in COUNTS]


def assess_case(case, guards):
    if case["family"] == "support_finance":
        return assess_dense(case, guards)
    return assess_family(case, guards)


def validate_case(case):
    scenario = build_scenario(case["spec"])
    guards = direct_sage(scenario.model, scenario.policy)
    result = assess_case(case, guards)
    if result["coverage_certificate"] != "SUFFICIENT_SAFE":
        raise ValueError(f"No sufficient certificate for {case['id']}")
    if result["missed"] or result["blocked"]:
        raise ValueError(f"Oracle mismatch for {case['id']}: {result}")
    return result


def digest_bytes(value):
    return hashlib.sha256(value).hexdigest()


def export_suite(output):
    output.mkdir(parents=True, exist_ok=False)
    entries = []
    for case in build_suite():
        result = validate_case(case)
        case_dir = output / case["id"]
        case_dir.mkdir()
        public_bytes = (json.dumps(case["public"], ensure_ascii=False, indent=2) + "\n").encode()
        model = {
            "id": case["id"], "family": case["family"], "dispatch_count": case["dispatch_count"],
            "labels": case["labels"], "actions": case["actions"], "spec": case["spec"],
        }
        model_bytes = (json.dumps(model, ensure_ascii=False, indent=2) + "\n").encode()
        (case_dir / "public_input.json").write_bytes(public_bytes)
        (case_dir / "confirmed_model.json").write_bytes(model_bytes)
        item = {
            "id": case["id"], "family": case["family"],
            "dispatch_count": case["dispatch_count"], "total_actions": len(case["actions"]),
            "dangerous_probes": result["dangerous_probes"],
            "benign_probes": result["benign_probes"],
            "direct_coverage_certificate": result["coverage_certificate"],
            "public_input_sha256": digest_bytes(public_bytes),
            "confirmed_model_sha256": digest_bytes(model_bytes),
        }
        manifest_bytes = (json.dumps(item, ensure_ascii=False, indent=2) + "\n").encode()
        (case_dir / "manifest.json").write_bytes(manifest_bytes)
        entries.append({**item, "manifest_sha256": digest_bytes(manifest_bytes)})
    manifest = {
        "schema_version": 1,
        "dataset_role": "composition-benchmark",
        "design": "6 business families x 6 nested dispatch counts",
        "families": list(FAMILIES),
        "counts": list(COUNTS),
        "workflow_tasks": len(entries),
        "independence_note": (
            "Levels within a family are nested and correlated; the suite has 36 authoring tasks "
            "but only six business-family clusters."
        ),
        "selection_note": (
            "Counts and deterministic SHA256 ordering are fixed independently of candidate outcomes."
        ),
        "generator_sha256": digest_bytes(Path(__file__).read_bytes()),
        "entries": entries,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("validate", "export", "summary"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    cases = build_suite()
    if args.mode == "summary":
        print(json.dumps({
            "families": list(FAMILIES), "counts": list(COUNTS),
            "workflow_tasks": len(cases),
            "total_actions": sum(len(case["actions"]) for case in cases),
            "actions_by_count": {count: sorted({len(case["actions"]) for case in cases
                                                if case["dispatch_count"] == count})
                                 for count in COUNTS},
        }, ensure_ascii=False, indent=2))
    elif args.mode == "validate":
        rows = [{"id": case["id"], **validate_case(case)} for case in cases]
        print(json.dumps({"validated": len(rows), "rows": rows}, ensure_ascii=False, indent=2))
    else:
        if args.output is None:
            parser.error("export requires --output")
        export_suite(args.output)


if __name__ == "__main__":
    main()
