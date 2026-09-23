"""Materialize derived business-family cases for review and artifact release."""

import hashlib
import json
from pathlib import Path

from .business_families import BUILDERS, build_family


ROOT = Path(__file__).resolve().parent / "derived_cases"


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    entries = []
    for count in (48, 64, 80):
        for family in BUILDERS:
            case = build_family(family, count)
            target = ROOT / case["id"]
            target.mkdir(exist_ok=False)
            public_bytes = encoded(case["public"])
            model_bytes = encoded(case["spec"])
            (target / "public_input.json").write_bytes(public_bytes)
            (target / "confirmed_model.json").write_bytes(model_bytes)
            manifest = {
                "id": case["id"],
                "family": family,
                "dataset_role": "controlled-derivative",
                "dispatch_count": count,
                "total_actions": len(case["actions"]),
                "target_tool": case["target_tool"],
                "labels": list(case["labels"]),
                "public_input_sha256": digest(public_bytes),
                "confirmed_model_sha256": digest(model_bytes),
                "note": "Researcher-authored controlled derivative; not an independently collected deployment.",
            }
            manifest_bytes = encoded(manifest)
            (target / "manifest.json").write_bytes(manifest_bytes)
            entries.append({**manifest, "manifest_sha256": digest(manifest_bytes)})
    index = {
        "schema_version": 1,
        "case_count": len(entries),
        "business_families": list(BUILDERS),
        "density_levels": [48, 64, 80],
        "unit_note": "Nine guard-authoring cases. Diagnostic probes are evaluation records, not additional cases.",
        "cases": entries,
    }
    (ROOT / "manifest.json").write_bytes(encoded(index))
    (ROOT / "README.md").write_text(
        "# Controlled derivative cases\n\n"
        "This directory materializes three researcher-authored business families at 48, 64, and 80 concrete effect calls. "
        "Each case separates the public Config-A drafting input from the verifier-side confirmed model. "
        "The cases share a composition template and must not be described as independent real-world deployments.\n\n"
        "There are nine guard-authoring cases. Counts of probes, events, or repair rounds are separate evaluation units.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
