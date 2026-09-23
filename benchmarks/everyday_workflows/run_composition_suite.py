"""One-shot MiMo runner for the frozen 6x6 composition suite."""

import argparse
import getpass
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from sage.v2.scenario import build_scenario

from .composition_suite import COUNTS, FAMILIES, assess_case, build_case
from .evaluate import parse_candidate
from .run import SYSTEM, fingerprint, request_once


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def evaluate(case, raw, max_states):
    try:
        guards = parse_candidate(case, raw)
    except (ValueError, TypeError) as error:
        return {"candidate_status": "FORMAT_ERROR", "verification_status": "NOT_RUN", "error": str(error)}
    scenario = build_scenario(case["spec"])
    assessment = assess_case(case, guards)
    certificate = assessment["coverage_certificate"]
    if certificate == "SUFFICIENT_SAFE":
        status, counterexample, reason = "PASS", None, None
        basis = "SUFFICIENT_ACTION_COVERAGE"
    elif assessment["missed"] > 0 and assessment["prefix_block_decisions"] == 0:
        # The diagnostic harness has already executed this prefix and action
        # against the reference policy.  Preserve its first concrete mismatch
        # as the witness instead of repeating a generic state-space search.
        status = "FAIL"
        counterexample = assessment["mismatches"][0]
        reason = None
        basis = "EXECUTABLE_DIAGNOSTIC_WITNESS"
    else:
        status, counterexample = "UNKNOWN", None
        reason = "Coverage certificate inconclusive; no unblocked fixed-probe miss; exhaustive BFS not run"
        basis = "INCONCLUSIVE_COVERAGE_AND_DIAGNOSTICS"
    return {
        "candidate_status": "VALID", "verification_status": status,
        "verification_basis": basis,
        "verification_error": reason,
        "counterexample": counterexample,
        **assessment,
    }


def write_report(path, manifest, rows):
    valid = [row for row in rows if row["evaluation"].get("candidate_status") == "VALID"]
    passed = [row for row in valid if row["evaluation"].get("verification_status") == "PASS"]
    dangerous = sum(row["evaluation"].get("dangerous_probes", 0) for row in valid)
    benign = sum(row["evaluation"].get("benign_probes", 0) for row in valid)
    missed = sum(row["evaluation"].get("missed", 0) for row in valid)
    blocked = sum(row["evaluation"].get("blocked", 0) for row in valid)
    lines = [
        "# MiMo composition-suite one-shot checkpoint", "",
        "Status: **COMPLETE**" if len(rows) == len(manifest["tasks"]) else "Status: **RUNNING**", "",
        f"Completed tasks: **{len(rows)}/{len(manifest['tasks'])}**; valid candidates: **{len(valid)}**; "
        f"trace PASS: **{len(passed)}/{len(valid) if valid else 0}**.",
        f"Diagnostic DER: **{dangerous-missed}/{dangerous}**; BBR: **{blocked}/{benign}**.", "",
        "| Family | Dispatches | Candidate | Verification | Missed/dangerous | Blocked/benign | Budget used |",
        "|---|---:|---|---|---:|---:|---:|",
    ]
    for row in rows:
        e = row["evaluation"]
        lines.append(
            f"| {row['family']} | {row['count']} | {e.get('candidate_status')} | "
            f"{e.get('verification_status')} | {e.get('missed', 0)}/{e.get('dangerous_probes', 0)} | "
            f"{e.get('blocked', 0)}/{e.get('benign_probes', 0)} | {row.get('effective_max_tokens')} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--families", nargs="+", choices=FAMILIES, default=list(FAMILIES))
    parser.add_argument("--counts", nargs="+", type=int, choices=COUNTS, default=list(COUNTS))
    parser.add_argument("--task", nargs="+", help="Optional exact composition task IDs")
    parser.add_argument("--model", default="mimo-v2.5")
    parser.add_argument("--base-url", default="https://token-plan-cn.xiaomimimo.com/v1")
    parser.add_argument("--initial-max-tokens", type=int, default=8192)
    parser.add_argument("--max-token-ceiling", type=int, default=32768)
    parser.add_argument("--max-states", type=int, default=5000)
    parser.add_argument("--omit-response-format", action="store_true")
    parser.add_argument("--api-timeout", type=int, default=180)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise SystemExit(f"Refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    os.environ["SAGE_API_KEY"] = getpass.getpass("MiMo API key: ")
    os.environ["SAGE_API_BASE_URL"] = args.base_url
    os.environ["SAGE_OMIT_RESPONSE_FORMAT"] = "1" if args.omit_response_format else "0"
    os.environ["SAGE_API_TIMEOUT_SECONDS"] = str(args.api_timeout)

    cases = [build_case(family, count) for family in args.families for count in args.counts]
    if args.task:
        by_id = {case["id"]: case for case in cases}
        if len(args.task) != len(set(args.task)) or set(args.task) - set(by_id):
            parser.error("Unknown or duplicate composition task ID")
        cases = [by_id[identity] for identity in args.task]
    source_files = tuple(Path(__file__).resolve().parent / name for name in (
        "composition_suite.py", "business_families.py", "dense.py", "run.py", "evaluate.py"))
    manifest = {
        "record_type": "manifest", "created_at": datetime.now(timezone.utc).isoformat(),
        "protocol": "composition-config-a-v1-one-shot", "model": args.model,
        "temperature": 0.2, "initial_max_tokens": args.initial_max_tokens,
        "max_token_ceiling": args.max_token_ceiling, "max_states": args.max_states,
        "verification_protocol": (
            "Use sufficient action-coverage certificate when available; otherwise run bounded "
            "counterexample search only for an unblocked executable diagnostic miss; else UNKNOWN."
        ),
        "truncation_policy": "double only after finish_reason=length",
        "retries": "no quality retries; transport recovery must be a separate recorded run",
        "response_format": "omitted" if args.omit_response_format else "json_object",
        "api_timeout_seconds": args.api_timeout,
        "tasks": [case["id"] for case in cases],
        "source_hashes": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in source_files},
    }
    rows = []
    jsonl = args.output_dir / "results.jsonl"
    with jsonl.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(manifest, ensure_ascii=False) + "\n")
        for case in cases:
            messages = [{"role": "system", "content": SYSTEM},
                        {"role": "user", "content": json.dumps(case["public"], ensure_ascii=False)}]
            attempts = []
            budget = args.initial_max_tokens
            while True:
                response = request_once(messages, args.model, 0.2, budget)
                attempts.append({"max_tokens": budget, **response})
                if not (response["transport_status"] == "OK" and response.get("finish_reason") == "length"):
                    break
                if budget >= args.max_token_ceiling:
                    break
                budget = min(budget * 2, args.max_token_ceiling)
            evaluation = {"candidate_status": "NOT_EVALUATED", "verification_status": "NOT_RUN"}
            if response["transport_status"] == "OK":
                if response.get("finish_reason") == "length":
                    evaluation["candidate_status"] = "TRUNCATED"
                else:
                    evaluation = evaluate(case, response["raw_content"], args.max_states)
            row = {
                "record_type": "candidate", "workflow": case["id"], "family": case["family"],
                "count": case["dispatch_count"], "total_actions": len(case["actions"]),
                "prompt_sha256": fingerprint(messages), "messages": messages,
                "attempts": attempts, "effective_max_tokens": budget, **response,
                "evaluation": evaluation,
            }
            rows.append(row)
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            atomic_json(args.output_dir / "checkpoint.json", {"manifest": manifest, "records": rows})
            write_report(args.output_dir / "report.md", manifest, rows)
            print(case["id"], response["transport_status"], evaluation.get("candidate_status"),
                  evaluation.get("verification_status"),
                  f"missed={evaluation.get('missed', '-')}", f"blocked={evaluation.get('blocked', '-')}", flush=True)


if __name__ == "__main__":
    main()
