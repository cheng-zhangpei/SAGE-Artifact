"""Config-A boundary stress test for implicit flows and side channels."""

import argparse
import hashlib
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .dataset import ROOT, load_implicit_cases

SYSTEM = """You are reviewing a security requirement for a tool-using service.
Read the ordinary business scenario and decide whether the described behavior should be blocked.
The policy goal is that the named secret must not be observable through the named channel.
Return exactly one JSON object:
{"decision":"DENY or ALLOW","risk_type":"one short category","reason":"one sentence"}
Use DENY when the secret can be learned through the observable behavior, even if the response
contains no secret field. Use ALLOW only when the observable behavior does not reveal the secret.
Do not propose guards, formulas, implementation details, or caveats. Do not answer UNKNOWN.
"""


def messages_for(case):
    user = {
        "title": case["title"], "business_scenario": case["story"],
        "secret": case["secret"], "observable_channel": case["observable"],
        "required_business_decision": "Should this behavior be blocked?",
    }
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)}]


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=pairs, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def request_once(messages, model, temperature, max_tokens):
    key = os.environ.get("SAGE_API_KEY")
    base = os.environ.get("SAGE_API_BASE_URL", "").rstrip("/")
    if not key or not base:
        raise ValueError("Set SAGE_API_KEY and SAGE_API_BASE_URL")
    parsed = urlparse(base)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("SAGE_API_BASE_URL must be a clean HTTPS API root")
    payload = {"model": model, "messages": messages, "temperature": temperature,
               "max_tokens": max_tokens, "response_format": {"type": "json_object"}}
    request = urllib.request.Request(
        base + "/chat/completions", data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return {"transport_status": "API_ERROR", "error": f"HTTP {error.code}"}
    except (OSError, ValueError):
        return {"transport_status": "API_ERROR", "error": "Transport or response decoding failure"}
    try:
        choice = body["choices"][0]
        raw = choice["message"]["content"]
        return {"transport_status": "OK", "raw_content": raw,
                "finish_reason": choice.get("finish_reason"), "usage": body.get("usage"),
                "response_model": body.get("model"), "response_id": body.get("id")}
    except (KeyError, IndexError, TypeError):
        return {"transport_status": "API_ERROR", "error": "Unsupported completion response shape"}


def evaluate(case, response):
    result = {"expected_decision": case["business_expected"], "expected_risk_type": case["channel"]}
    if response.get("transport_status") != "OK":
        return result | {"status": "API_ERROR"}
    if response.get("finish_reason") == "length":
        return result | {"status": "TRUNCATED"}
    try:
        answer = strict_json(response["raw_content"])
        if set(answer) != {"decision", "risk_type", "reason"}:
            raise ValueError("wrong output fields")
        if answer["decision"] not in {"DENY", "ALLOW"} or not all(isinstance(answer[key], str) and answer[key] for key in answer):
            raise ValueError("invalid boundary answer")
        correct = answer["decision"] == case["business_expected"]
        return result | {"status": "VALID", "correct": correct, "answer": answer}
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        return result | {"status": "FORMAT_ERROR", "error": str(error)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-tokens", type=int, default=1024)
    args = parser.parse_args(argv)
    cases = load_implicit_cases()
    source_hash = hashlib.sha256((ROOT / "implicit_flows.yaml").read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        output.write(json.dumps({"record_type": "manifest", "schema_version": 1,
            "protocol": "config-a-implicit-boundary-one-shot", "model": args.model,
            "created_at": datetime.now(timezone.utc).isoformat(), "case_count": len(cases),
            "source_hash": source_hash, "retries": 0, "sage_verdict": "NOT_APPLICABLE"}, ensure_ascii=False) + "\n")
        for case in cases:
            messages = messages_for(case)
            response = request_once(messages, args.model, args.temperature, args.max_tokens)
            row = {"record_type": "case", "case": case["id"], "messages": messages,
                   "prompt_sha256": hashlib.sha256(json.dumps(messages, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
                   **response, "evaluation": evaluate(case, response)}
            output.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
            output.flush()


if __name__ == "__main__":
    main()
