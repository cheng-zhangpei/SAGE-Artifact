"""Report sink fields absent from the textual inputs of earlier AI nodes.

This is a recall aid for manual review.  It deliberately does not infer data
identity across renames and does not assign labels or policies.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


FIELD_PATTERNS = [
    re.compile(r"\$json(?:\[['\"]([^'\"]+)['\"]\]|\.([A-Za-z_$][\w$]*))"),
    re.compile(r"\.json(?:\[['\"]([^'\"]+)['\"]\]|\.([A-Za-z_$][\w$]*))"),
]


def fields(parameters: dict) -> set[str]:
    raw = json.dumps(parameters, ensure_ascii=False, sort_keys=True)
    answer = set()
    for pattern in FIELD_PATTERNS:
        for match in pattern.finditer(raw):
            answer.add(match.group(1) or match.group(2))
    return answer


def main():
    p = argparse.ArgumentParser(); p.add_argument("--root", type=Path, required=True); p.add_argument("--output", type=Path, required=True); a = p.parse_args()
    sample = json.loads((a.root / "negative_audit_structural.json").read_text(encoding="utf-8"))
    rows = []
    for item in sample["workflows"]:
        if not item["broad_candidate"]: continue
        wf = json.loads((a.root / "workflows" / f"{item['id']}.json").read_text(encoding="utf-8"))["workflow"]["workflow"]
        nodes = {n["name"]: n for n in wf.get("nodes", []) if isinstance(n.get("name"), str)}
        for finding in item["broad_bypass_findings"]:
            sink_fields = fields(nodes[finding["sink"]].get("parameters", {}))
            ai_names = sorted({path[0] for path in finding["ai_paths"] if path and path[0] in nodes})
            ai_fields = set().union(*(fields(nodes[name].get("parameters", {})) for name in ai_names)) if ai_names else set()
            omitted = sorted(sink_fields - ai_fields)
            rows.append({"id": item["id"], "name": item["name"], "stratum": item["stratum"], "sink": finding["sink"],
                         "earlier_ai_nodes": ai_names, "sink_fields": sorted(sink_fields), "ai_input_fields": sorted(ai_fields),
                         "sink_fields_not_named_in_ai_inputs": omitted,
                         "status": "context_projection_candidate" if omitted else "no_lexical_field_difference",
                         "warning": "lexical field comparison only; aliases, implicit item flow, data identity, labels and policy require review"})
    counts = Counter((x["stratum"], x["status"]) for x in rows)
    result = {"definition": "lexical comparison of sink parameter fields against earlier AI parameter fields",
              "counts": [{"stratum": k[0], "status": k[1], "sink_findings": v} for k,v in sorted(counts.items())], "findings": rows}
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["counts"]))


if __name__ == "__main__": main()
