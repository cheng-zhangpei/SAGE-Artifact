"""Export compact, paper-facing tables from the frozen workflow study."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    args = p.parse_args()
    root = args.root
    manifest = json.loads((root / "candidate_final_status.json").read_text(encoding="utf-8"))
    inventory = {x["id"]: x for x in json.loads((root / "structural_inventory.json").read_text(encoding="utf-8"))}
    results = {x["id"]: x for x in json.loads((root / "reviewed_slice_results.json").read_text(encoding="utf-8"))}
    with (root / "candidate_results.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["id", "name", "author", "views", "status", "subtype", "structure_fingerprint",
                  "ctx_collision_classes", "ctx_blocked_benign_events", "event_collision_classes",
                  "event_blocked_benign_events", "compiled_verified", "review_evidence"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in manifest["candidates"]:
            checked = results.get(item["id"])
            writer.writerow({
                "id": item["id"], "name": item["name"], "author": item.get("author"),
                "views": inventory[item["id"]].get("total_views"), "status": item["final_status"],
                "subtype": item.get("subtype"), "structure_fingerprint": item["structure_fingerprint"],
                "ctx_collision_classes": checked["observations"]["ctx"]["collision_classes"] if checked else "",
                "ctx_blocked_benign_events": checked["observations"]["ctx"]["blocked_benign_send_events"] if checked else "",
                "event_collision_classes": checked["observations"]["event"]["collision_classes"] if checked else "",
                "event_blocked_benign_events": checked["observations"]["event"]["blocked_benign_send_events"] if checked else "",
                "compiled_verified": checked["compiled_verified"] if checked else "",
                "review_evidence": item["review_evidence"],
            })
    sample = json.loads((root / "negative_audit_structural.json").read_text(encoding="utf-8"))
    with (root / "negative_audit_sample.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["id", "name", "stratum", "source_sha256", "structure_fingerprint", "broad_candidate", "candidate_sinks", "semantic_review_status"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in sample["workflows"]:
            writer.writerow({
                "id": item["id"], "name": item["name"], "stratum": item["stratum"],
                "source_sha256": item["source_sha256"], "structure_fingerprint": item["structure_fingerprint"],
                "broad_candidate": item["broad_candidate"],
                "candidate_sinks": "; ".join(x["sink"] for x in item["broad_bypass_findings"]),
                "semantic_review_status": "pending" if item["broad_candidate"] else "not_selected_by_broad_check",
            })
    print(json.dumps({"candidate_rows": len(manifest["candidates"]), "negative_audit_rows": len(sample["workflows"])}))


if __name__ == "__main__":
    main()
