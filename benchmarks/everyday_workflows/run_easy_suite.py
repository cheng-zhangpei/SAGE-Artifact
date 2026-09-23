"""Run the frozen W01-W36 Config-A suite once with checkpoints and no hidden retries."""

import argparse
import getpass
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


SAGE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SAGE_ROOT))

from benchmarks.everyday_workflows.dataset import load_workflows  # noqa: E402
from benchmarks.everyday_workflows.evaluate import evaluate_candidate  # noqa: E402
from benchmarks.everyday_workflows.run import (  # noqa: E402
    fingerprint,
    messages_for,
    provenance,
    request_once,
)


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def write_report(path, manifest, records):
    ok = [row for row in records if row["transport_status"] == "OK"]
    evaluated = [row for row in ok if row["evaluation"]["candidate_status"] != "TRUNCATED"]
    valid = [row for row in evaluated if row["evaluation"]["candidate_status"] == "VALID"]
    passes = [row for row in valid if row["evaluation"]["verification_status"] == "PASS"]
    total_pairs = sum(row["evaluation"].get("total_pairs", 0) for row in valid)
    correct_pairs = sum(row["evaluation"].get("correct_pairs", 0) for row in valid)
    danger = sum(row["evaluation"].get("total_pairs", 0) for row in valid)
    denied_danger = sum(
        sum(p["decision"] == "DENY" for p in row["evaluation"].get("probes", []) if p["class"] == "danger")
        for row in valid
    )
    benign = sum(row["evaluation"].get("total_pairs", 0) for row in valid)
    denied_benign = sum(
        sum(p["decision"] == "DENY" for p in row["evaluation"].get("probes", []) if p["class"] == "benign")
        for row in valid
    )
    def attempts_of(row):
        return row.get("attempts") or [row]

    usage = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        usage[key] = sum(
            (attempt.get("usage") or {}).get(key, 0) or 0
            for row in records for attempt in attempts_of(row)
            if attempt.get("transport_status") == "OK"
        )
    lines = [
        "# MiMo W01-W36 one-shot report",
        "",
        "Status: **COMPLETE**" if len(records) == len(manifest["workflows"]) else "Status: **RUNNING**",
        "",
        f"Protocol: `{manifest['protocol']}`; model: `{manifest['model']}`; "
        f"temperature: {manifest['temperature']}; max output tokens: {manifest['max_tokens']}.",
        "Each workflow receives one model call. Transport failures are recorded and are not retried in this run.",
        "",
        f"Completed workflows: **{len(records)}/{len(manifest['workflows'])}**; successful responses: **{len(ok)}**; "
        f"valid candidates: **{len(valid)}**; trace-level PASS: **{len(passes)}/{len(valid) if valid else 0}**.",
        f"Correct diagnostic pairs: **{correct_pairs}/{total_pairs}**.",
        f"Probe DER: **{denied_danger}/{danger}**; probe BBR: **{denied_benign}/{benign}**.",
        f"Provider-reported tokens: prompt {usage['prompt_tokens']}, completion {usage['completion_tokens']}, "
        f"total {usage['total_tokens']}.",
        "",
        "| Workflow | Transport | Candidate | Verification | Correct pairs | DER | BBR | Tokens |",
        "|---|---|---|---|---:|---:|---:|---:|",
    ]
    for row in records:
        evaluation = row["evaluation"]
        pairs = evaluation.get("total_pairs", 0)
        lines.append(
            f"| {row['workflow']} | {row['transport_status']} | {evaluation.get('candidate_status')} | "
            f"{evaluation.get('verification_status')} | {evaluation.get('correct_pairs', 0)}/{pairs} | "
            f"{evaluation.get('probe_der', 0):.1%} | {evaluation.get('probe_bbr', 0):.1%} | "
            f"{sum((attempt.get('usage') or {}).get('total_tokens', 0) or 0 for attempt in attempts_of(row))} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="mimo-v2.5")
    parser.add_argument("--base-url", default="https://token-plan-cn.xiaomimimo.com/v1")
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--max-token-ceiling", type=int, default=16384)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--omit-response-format", action="store_true")
    parser.add_argument("--api-timeout", type=int, default=180)
    parser.add_argument("--max-states", type=int, default=20000)
    parser.add_argument("--workflow", nargs="+", help="Optional ordered workflow subset")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.max_token_ceiling < args.max_tokens:
        parser.error("--max-token-ceiling must be at least --max-tokens")
    if args.output_dir.exists():
        raise SystemExit(f"Refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    os.environ["SAGE_API_KEY"] = getpass.getpass("MiMo API key: ")
    os.environ["SAGE_API_BASE_URL"] = args.base_url
    os.environ["SAGE_OMIT_RESPONSE_FORMAT"] = "1" if args.omit_response_format else "0"
    os.environ["SAGE_API_TIMEOUT_SECONDS"] = str(args.api_timeout)

    all_workflows = load_workflows()
    by_id = {workflow["id"]: workflow for workflow in all_workflows}
    selected = args.workflow or list(by_id)
    if len(selected) != len(set(selected)) or set(selected) - set(by_id):
        parser.error("Unknown or duplicate workflow ID")
    workflows = [by_id[identity] for identity in selected]
    manifest = {
        "record_type": "manifest",
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "protocol": "config-a-v2-no-formal-hints-one-shot",
        "model": args.model,
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "max_token_ceiling": args.max_token_ceiling,
        "truncation_policy": "double output budget only after finish_reason=length",
        "max_states": args.max_states,
        "repetitions": 1,
        "retries": 0,
        "response_format": "omitted" if args.omit_response_format else "json_object",
        "api_timeout_seconds": args.api_timeout,
        "workflows": [workflow["id"] for workflow in workflows],
        "source_hashes": provenance(),
    }
    records = []
    jsonl = args.output_dir / "candidates.jsonl"
    with jsonl.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(manifest, ensure_ascii=False) + "\n")
        stream.flush()
        for workflow in workflows:
            messages = messages_for(workflow)
            attempts = []
            budget = args.max_tokens
            while True:
                response = request_once(messages, args.model, args.temperature, budget)
                attempts.append({"max_tokens": budget, **response})
                if not (response["transport_status"] == "OK" and response.get("finish_reason") == "length"):
                    break
                if budget >= args.max_token_ceiling:
                    break
                budget = min(budget * 2, args.max_token_ceiling)
            evaluation = {"candidate_status": "NOT_EVALUATED", "verification_status": "NOT_RUN"}
            if response["transport_status"] == "OK":
                if response.get("finish_reason") == "length":
                    evaluation = {"candidate_status": "TRUNCATED", "verification_status": "NOT_RUN"}
                else:
                    evaluation = evaluate_candidate(workflow, response["raw_content"], args.max_states)
            row = {
                "record_type": "candidate",
                "workflow": workflow["id"],
                "prompt_sha256": fingerprint(messages),
                "messages": messages,
                "attempts": attempts,
                "effective_max_tokens": budget,
                **response,
                "evaluation": evaluation,
            }
            records.append(row)
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            atomic_json(args.output_dir / "checkpoint.json", {"manifest": manifest, "records": records})
            write_report(args.output_dir / "report.md", manifest, records)
            print(
                workflow["id"], response["transport_status"],
                evaluation.get("candidate_status"), evaluation.get("verification_status"),
                f"pairs={evaluation.get('correct_pairs', 0)}/{evaluation.get('total_pairs', 0)}",
                flush=True,
            )


if __name__ == "__main__":
    main()
