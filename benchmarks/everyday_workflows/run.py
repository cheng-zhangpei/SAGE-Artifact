"""Config-A-only prompts, offline evaluation, and opt-in one-shot API runs."""

import argparse
import hashlib
import http.client
import json
import os
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .dataset import ROOT, drafting_input, load_workflows
from .evaluate import evaluate_candidate, evaluate_direct, strict_json

SYSTEM = """You are a security engineer drafting runtime information-flow guards.
Use only the provided scenario, natural-language tool descriptions and security policy.
Draft guards for the entire workflow that enforce the policy while preserving permitted uses.
Return only {"guards":[{"agent":"...","tool":"...","params":{},"forbidden_labels":["..."]}]}.
Copy agent, tool and the complete params object exactly from a listed concrete call.
The forbidden_labels field lists data categories that must cause this matching call
to be rejected when present in the information it handles. Any listed category triggers rejection.
Use only declared labels. Do not use wildcards, additional keys, Markdown or explanations.
An empty guard set is {"guards":[]}."""


def messages_for(workflow):
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(drafting_input(workflow), ensure_ascii=False)}]


def fingerprint(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def provenance():
    names = ("catalog.yaml", "extension.yaml", "boundaries.yaml", "dataset.py", "evaluate.py", "run.py")
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}


def request_once(messages, model, temperature, max_tokens):
    key = os.environ.get("SAGE_API_KEY")
    base = os.environ.get("SAGE_API_BASE_URL", "").rstrip("/")
    if not key or not base:
        raise ValueError("Set SAGE_API_KEY and SAGE_API_BASE_URL in the process environment")
    parsed = urlparse(base)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("SAGE_API_BASE_URL must be an HTTPS API root without credentials or query")
    payload = {"model": model, "messages": messages, "temperature": temperature,
               "max_tokens": max_tokens}
    if os.environ.get("SAGE_OMIT_RESPONSE_FORMAT") != "1":
        payload["response_format"] = {"type": "json_object"}
    request = urllib.request.Request(
        base + "/chat/completions", data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, method="POST",
    )
    try:
        timeout = int(os.environ.get("SAGE_API_TIMEOUT_SECONDS", "180"))
        tls = ssl.create_default_context()
        with urllib.request.urlopen(request, timeout=timeout, context=tls) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        try:
            detail = error.read().decode("utf-8", errors="replace")[:1000]
        except OSError:
            detail = ""
        return {"transport_status": "API_ERROR", "error": f"HTTP {error.code}",
                "status_code": error.code, "error_detail": detail}
    except (OSError, ValueError, http.client.IncompleteRead) as error:
        # Some OpenAI-compatible gateways occasionally close an urllib TLS
        # response without a close-notify. Retry that transport failure through
        # requests while preserving the exact payload and response parser.
        if "EOF occurred in violation of protocol" in str(error):
            try:
                import requests
            except ImportError as fallback_error:
                return {"transport_status": "API_ERROR", "error": "Transport fallback unavailable",
                        "error_class": type(fallback_error).__name__,
                        "transport_fallback": "requests"}

            try:
                fallback = requests.post(
                    base + "/chat/completions", json=payload,
                    headers={"Authorization": f"Bearer {key}"}, timeout=timeout,
                    verify=True,
                )
                if fallback.status_code >= 400:
                    return {"transport_status": "API_ERROR", "error": f"HTTP {fallback.status_code}",
                            "status_code": fallback.status_code,
                            "error_detail": fallback.text[:1000], "transport_fallback": "requests"}
                body = fallback.json()
            except (requests.RequestException, ValueError) as fallback_error:
                return {"transport_status": "API_ERROR", "error": "Transport or response decoding failure",
                        "error_class": type(fallback_error).__name__,
                        "error_detail": str(fallback_error)[:1000], "transport_fallback": "requests"}
        else:
            return {"transport_status": "API_ERROR", "error": "Transport or response decoding failure",
                    "error_class": type(error).__name__}
    try:
        choice = body["choices"][0]
        raw = choice["message"]["content"]
        if not isinstance(raw, str):
            raise ValueError("Missing text content")
        return {"transport_status": "OK", "raw_content": raw,
                "finish_reason": choice.get("finish_reason"), "usage": body.get("usage"),
                "response_model": body.get("model"), "response_id": body.get("id")}
    except (KeyError, IndexError, TypeError, ValueError):
        return {"transport_status": "API_ERROR", "error": "Unsupported completion response shape"}


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prompts", "direct", "evaluate", "live"))
    parser.add_argument("--workflow", nargs="+", help="Default: all workflows")
    parser.add_argument("--output", type=Path, required=True, help="New JSONL file; never overwrite")
    parser.add_argument("--candidates", type=Path, help="JSONL records: workflow, raw_content")
    parser.add_argument("--model", help="Required exact provider model ID for live runs")
    parser.add_argument("--repetitions", type=positive, default=1)
    parser.add_argument("--max-states", type=positive, default=20000)
    parser.add_argument("--max-tokens", type=positive, default=8192)
    parser.add_argument("--temperature", type=float, default=0.2)
    args = parser.parse_args(argv)
    workflows = {workflow["id"]: workflow for workflow in load_workflows()}
    selected = args.workflow or list(workflows)
    if len(set(selected)) != len(selected) or set(selected) - set(workflows):
        parser.error("Unknown or duplicate workflow IDs")
    if args.mode == "live" and (not args.model or not os.environ.get("SAGE_API_KEY") or not os.environ.get("SAGE_API_BASE_URL")):
        parser.error("Live mode requires --model, SAGE_API_KEY and SAGE_API_BASE_URL")
    if args.mode == "evaluate" and not args.candidates:
        parser.error("Evaluate mode requires --candidates")
    candidates = []
    if args.mode == "evaluate":
        for line in args.candidates.read_text(encoding="utf-8").splitlines():
            row = strict_json(line)
            if row.get("workflow") not in workflows or not isinstance(row.get("raw_content"), str):
                parser.error("Each candidate needs a known workflow and string raw_content")
            if row["workflow"] in selected:
                candidates.append(row)
        if not candidates:
            parser.error("No matching candidates")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        def emit(row):
            output.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
            output.flush()

        emit({"record_type": "manifest", "schema_version": 1, "mode": args.mode,
              "created_at": datetime.now(timezone.utc).isoformat(), "workflows": selected,
              "source_hashes": provenance(), "protocol": "config-a-v2-no-formal-hints-one-shot",
              "model": args.model, "temperature": args.temperature, "max_tokens": args.max_tokens,
              "max_states": args.max_states, "repetitions": args.repetitions,
              "boundary_execution": "NOT_IMPLEMENTED", "retries": 0})
        if args.mode == "evaluate":
            for index, row in enumerate(candidates):
                emit({"record_type": "candidate", "candidate_index": index, **row,
                      "evaluation": evaluate_candidate(workflows[row["workflow"]], row["raw_content"], args.max_states)})
            return
        for identity in selected:
            workflow = workflows[identity]
            messages = messages_for(workflow)
            common = {"workflow": identity, "messages": messages, "prompt_sha256": fingerprint(messages)}
            if args.mode == "prompts":
                emit({"record_type": "prompt", **common})
            elif args.mode == "direct":
                emit({"record_type": "baseline", **common, "evaluation": evaluate_direct(workflow, args.max_states)})
            else:
                for repetition in range(1, args.repetitions + 1):
                    response = request_once(messages, args.model, args.temperature, args.max_tokens)
                    evaluation = {"candidate_status": "NOT_EVALUATED", "verification_status": "NOT_RUN"}
                    if response["transport_status"] == "OK":
                        if response["finish_reason"] == "length":
                            evaluation["candidate_status"] = "TRUNCATED"
                        else:
                            evaluation = evaluate_candidate(workflow, response["raw_content"], args.max_states)
                    emit({"record_type": "candidate", **common, "repetition": repetition,
                          **response, "evaluation": evaluation})
                    if response["transport_status"] != "OK":
                        raise SystemExit("API error recorded; stopped without retry")


if __name__ == "__main__":
    main()
