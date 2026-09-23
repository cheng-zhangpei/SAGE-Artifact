"""Run a deterministic broad bypass check over the frozen negative-audit sample.

This is a recall-oriented structural check.  A hit means that an external action
has both an AI ancestor and a non-AI source-to-sink path that avoids every AI
node.  It is not yet an information-flow collision: field use, contracts,
labels, policy, and equal resolved actions still require review.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import deque
from pathlib import Path

from analyze import AI, CHANNELS, REF


def is_ai(node: dict) -> bool:
    typ = node.get("type", "")
    return bool(AI.search(typ) or ".lmChat" in typ or ".embeddings" in typ)


def is_external_action(node: dict) -> bool:
    typ = node.get("type", "").lower()
    op = str(node.get("parameters", {}).get("operation", "")).lower()
    channel = any(x in typ for x in CHANNELS)
    storage = any(x in typ for x in ("googledrive", "awss3", "dropbox", "ftp", "onedrive"))
    return ((channel and "trigger" not in typ and op in ("send", "reply", "sendandwait", "post", "create", "upload", ""))
            or (storage and op in ("upload", "create", "copy", "share", "")))


def shortest_path(edges: dict[str, set[str]], start: str, goal: str, forbidden: set[str]) -> list[str] | None:
    q = deque([(start, [start])])
    seen = {start}
    while q:
        at, path = q.popleft()
        if at == goal:
            return path
        for nxt in sorted(edges.get(at, ())):
            if nxt in seen or (nxt in forbidden and nxt != goal):
                continue
            seen.add(nxt)
            q.append((nxt, [*path, nxt]))
    return None


def inspect(workflow_doc: dict, sampled: dict) -> dict:
    nodes = {n["name"]: n for n in workflow_doc.get("nodes", []) if isinstance(n.get("name"), str)}
    edges = {n: set() for n in nodes}
    edge_kinds: dict[tuple[str, str], set[str]] = {}
    def add(a: str, b: str, kind: str) -> None:
        if a in nodes and b in nodes:
            edges[a].add(b)
            edge_kinds.setdefault((a, b), set()).add(kind)
    for origin, ports in (workflow_doc.get("connections") or {}).items():
        if not isinstance(ports, dict):
            continue
        for groups in ports.values():
            if not isinstance(groups, list):
                continue
            for group in groups:
                for edge in group or []:
                    add(origin, edge.get("node"), "connection")
    for name, node in nodes.items():
        raw = json.dumps(node.get("parameters", {}), ensure_ascii=False, sort_keys=True)
        for match in REF.finditer(raw):
            add(match.group(1) or match.group(2), name, "named_expression")
    indegree = {n: 0 for n in nodes}
    for targets in edges.values():
        for target in targets:
            indegree[target] += 1
    roots = sorted(n for n, degree in indegree.items() if degree == 0 and not is_ai(nodes[n]))
    ais = {n for n in nodes if is_ai(nodes[n])}
    sinks = [n for n in nodes if is_external_action(nodes[n])]
    findings = []
    for sink in sorted(sinks):
        ai_paths = [p for a in sorted(ais) if (p := shortest_path(edges, a, sink, set()))]
        bypass_paths = [p for root in roots if (p := shortest_path(edges, root, sink, ais))]
        if not ai_paths or not bypass_paths:
            continue
        sink_raw = json.dumps(nodes[sink].get("parameters", {}), ensure_ascii=False, sort_keys=True)
        refs = sorted({a or b for a, b in REF.findall(sink_raw)})
        findings.append({
            "sink": sink, "sink_type": nodes[sink].get("type"),
            "ai_paths": ai_paths[:5], "non_ai_bypass_paths": bypass_paths[:10],
            "sink_named_references": refs,
            "status": "broad_candidate_requires_field_and_contract_review",
        })
    return {
        **sampled, "broad_bypass_findings": findings,
        "broad_candidate": bool(findings),
        "interpretation": "recall-oriented structural hit; not a SAGE collision",
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--sample", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    sample = json.loads(args.sample.read_text(encoding="utf-8"))
    rows = []
    for item in sample["samples"]:
        doc = json.loads((args.root / "workflows" / f"{item['id']}.json").read_text(encoding="utf-8"))["workflow"]["workflow"]
        rows.append(inspect(doc, item))
    by_stratum = {}
    for stratum in sorted({x["stratum"] for x in rows}):
        members = [x for x in rows if x["stratum"] == stratum]
        by_stratum[stratum] = {"sampled": len(members), "broad_candidates": sum(x["broad_candidate"] for x in members)}
    result = {
        "schema_version": 1, "seed": sample["seed"],
        "definition": "external sink with an AI ancestor and a non-AI root-to-sink path avoiding AI, using graph and named-expression edges",
        "warning": "broad candidates need exact field, contract, label, policy, and observation review",
        "counts": by_stratum, "workflows": rows,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(by_stratum))


if __name__ == "__main__":
    main()
