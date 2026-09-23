"""Find source references consumed by a sink that cannot reach an earlier AI.

This conservative subcheck uses both n8n connections and named expressions.  A
hit is still a dependency-review candidate rather than a collision claim.
"""
from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path

from analyze import REF


def reachable(edges, start, goal):
    queue, seen = deque([start]), {start}
    while queue:
        at = queue.popleft()
        if at == goal:
            return True
        for nxt in edges.get(at, ()):
            if nxt not in seen:
                seen.add(nxt); queue.append(nxt)
    return False


def main():
    p = argparse.ArgumentParser(); p.add_argument("--root", type=Path, required=True); p.add_argument("--output", type=Path, required=True); a = p.parse_args()
    sample = json.loads((a.root / "negative_audit_structural.json").read_text(encoding="utf-8"))
    output = []
    for item in sample["workflows"]:
        if not item["broad_candidate"]:
            continue
        wf = json.loads((a.root / "workflows" / f"{item['id']}.json").read_text(encoding="utf-8"))["workflow"]["workflow"]
        nodes = {n["name"]: n for n in wf.get("nodes", []) if isinstance(n.get("name"), str)}
        edges = {name: set() for name in nodes}
        for origin, ports in (wf.get("connections") or {}).items():
            if not isinstance(ports, dict): continue
            for groups in ports.values():
                if not isinstance(groups, list): continue
                for group in groups:
                    for edge in group or []:
                        if origin in nodes and edge.get("node") in nodes: edges[origin].add(edge["node"])
        for name, node in nodes.items():
            raw = json.dumps(node.get("parameters", {}), ensure_ascii=False, sort_keys=True)
            for m in REF.finditer(raw):
                source = m.group(1) or m.group(2)
                if source in nodes: edges[source].add(name)
        for finding in item["broad_bypass_findings"]:
            sink = finding["sink"]
            earlier_ai = {path[0] for path in finding["ai_paths"]}
            refs = finding["sink_named_references"]
            independent = [ref for ref in refs if ref not in earlier_ai and not any(
                reachable(edges, ref, ai) or reachable(edges, ai, ref) for ai in earlier_ai)]
            if independent:
                output.append({"id": item["id"], "name": item["name"], "stratum": item["stratum"], "sink": sink,
                               "sink_named_references": refs, "references_without_path_to_earlier_ai": independent,
                               "status": "explicit_bypass_candidate_requires_contract_policy_review"})
    result = {"definition": "sink named reference whose source has no graph/expression path to an earlier AI on the same sink path",
              "warning": "not a collision result", "count": len(output), "findings": output}
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"count": len(output), "workflow_count": len({x['id'] for x in output})}))


if __name__ == "__main__": main()
