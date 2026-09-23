"""Run the SAGE LLM experiment with auditable Config A/C inputs.

Config A exposes only tool identity and parameters. Config C additionally
exposes the human-confirmed ``reads``, ``writes``, and ``gen`` semantics. All
other prompt content is identical so the comparison isolates that structure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, Sequence

from experiments.metrics import (
    compute_unconstrained_domains,
    evaluate_constraints,
    unsafe_reachable_states,
)
from experiments.prompt_builder import (
    build_counterexample_user_prompt,
    build_initial_user_prompt,
    build_self_review_user_prompt,
    build_system_prompt,
    build_verdict_only_user_prompt,
)
from sage.v2.counterexample import (
    Counterexample,
    SearchLimitExceeded,
    counterexample_to_llm_json,
    shortest_counterexample,
)
from sage.v2.guards import Constraint, ParamFilter, semantic_normalize
from sage.v2.scenario import build_scenario
from sage.v2.semantics import forbidden_targets_of_action
from sage.v2.synthesis import direct_sage


DEFAULT_MODEL = os.environ.get("SAGE_LLM_MODEL", "mimo-v2.5-pro")
LLM_TEMPERATURE = 0.2
LLM_MAX_TOKENS = 4096 * 4
RESULT_SCHEMA_VERSION = 3

CONFIG_METADATA = {
    "A": {
        "name": "natural_language_tool_semantics",
        "tool_schema_fields": ["agent", "tool", "params"],
        "description": (
            "Natural-language scenario description plus tool identity and "
            "parameters; no structured reads/writes/gen fields."
        ),
    },
    "C": {
        "name": "structured_data_flow_semantics",
        "tool_schema_fields": [
            "agent",
            "tool",
            "params",
            "reads",
            "writes",
            "gen",
        ],
        "description": (
            "The same input as Config A plus human-confirmed structured "
            "reads/writes/gen fields."
        ),
    },
}

DEFAULT_SCENARIOS = tuple(
    f"experiments/scenarios/s{index}_full" for index in range(1, 10)
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_scenario(scenario_dir):
    scenario_path = Path(scenario_dir)
    with open(scenario_path / "scenario.json", "r", encoding="utf-8") as file:
        spec = json.load(file)
    with open(scenario_path / "description.md", "r", encoding="utf-8") as file:
        description = file.read()
    return build_scenario(spec), description, spec


def build_tools_schema(scenario, config: str) -> list:
    """Build the only input component that differs between Config A and C."""
    config = config.upper()
    if config not in CONFIG_METADATA:
        raise ValueError(f"unsupported config: {config}")

    tools = []
    for action in scenario.model.actions:
        item = {
            "agent": action.agent,
            "tool": action.tool,
            "params": dict(action.params_items),
        }
        if config == "C":
            item.update(
                {
                    "reads": sorted(str(loc) for loc in action.reads),
                    "writes": sorted(str(loc) for loc in action.writes),
                    "gen": sorted(action.gen),
                }
            )
        tools.append(item)
    return tools


class CandidateFormatError(ValueError):
    """The LLM response is JSON, but not a valid SAGE candidate artifact."""

    def __init__(self, message: str, candidate_json=None):
        super().__init__(message)
        self.candidate_json = candidate_json


def llm_json_to_constraints(llm_output):
    if not isinstance(llm_output, dict):
        raise CandidateFormatError(
            'candidate must be an object of the form {"guards":[...]}',
            llm_output,
        )
    if set(llm_output) != {"guards"}:
        raise CandidateFormatError(
            'candidate top-level keys must be exactly ["guards"]',
            llm_output,
        )

    guards_list = llm_output["guards"]
    if not isinstance(guards_list, list):
        raise CandidateFormatError(
            'candidate field "guards" must be an array', llm_output
        )

    constraints = []
    required_fields = {"agent", "tool", "params", "forbidden_labels"}
    scalar_types = (str, int, float, bool, type(None))

    for index, guard in enumerate(guards_list):
        if not isinstance(guard, dict):
            raise CandidateFormatError(
                f"guard[{index}] must be an object", llm_output
            )

        fields = set(guard)
        if fields != required_fields:
            missing = sorted(required_fields - fields)
            extra = sorted(fields - required_fields)
            raise CandidateFormatError(
                f"guard[{index}] has invalid fields; "
                f"missing={missing}, extra={extra}",
                llm_output,
            )

        agent = guard["agent"]
        tool = guard["tool"]
        params = guard["params"]
        forbidden_labels = guard["forbidden_labels"]

        if not isinstance(agent, str) or not agent:
            raise CandidateFormatError(
                f"guard[{index}].agent must be a non-empty string",
                llm_output,
            )
        if not isinstance(tool, str) or not tool:
            raise CandidateFormatError(
                f"guard[{index}].tool must be a non-empty string",
                llm_output,
            )
        if not isinstance(params, dict):
            raise CandidateFormatError(
                f"guard[{index}].params must be an object", llm_output
            )
        for key, value in params.items():
            if not isinstance(key, str) or not key:
                raise CandidateFormatError(
                    f"guard[{index}].params keys must be non-empty strings",
                    llm_output,
                )
            if not isinstance(value, scalar_types):
                raise CandidateFormatError(
                    f"guard[{index}].params[{key!r}] must be a JSON scalar",
                    llm_output,
                )
            if value == "*":
                raise CandidateFormatError(
                    f"guard[{index}].params[{key!r}] uses forbidden wildcard '*'",
                    llm_output,
                )
        if not isinstance(forbidden_labels, list) or not all(
            isinstance(label, str) and label for label in forbidden_labels
        ):
            raise CandidateFormatError(
                f"guard[{index}].forbidden_labels must be an array of "
                "non-empty strings",
                llm_output,
            )

        param_filter = ParamFilter(
            exact_patterns=(tuple(sorted(params.items())),),
            match_all=False,
        )
        constraints.append(
            Constraint(
                agent=agent,
                tool=tool,
                param_filter=param_filter,
                forbidden_labels=frozenset(forbidden_labels),
                name="llm_generated",
            )
        )
    return constraints


def constraints_to_json(constraints: Iterable[Constraint]) -> list:
    """Serialize parsed guards so every reported result remains auditable."""
    serialized = []
    for constraint in constraints:
        serialized.append(
            {
                "agent": constraint.agent,
                "tool": constraint.tool,
                "param_filter": {
                    "exact_patterns": [
                        dict(pattern)
                        for pattern in constraint.param_filter.exact_patterns
                    ],
                    "wildcard_patterns": [
                        dict(pattern)
                        for pattern in constraint.param_filter.wildcard_patterns
                    ],
                    "match_all": constraint.param_filter.match_all,
                },
                "forbidden_labels": sorted(constraint.forbidden_labels),
                "name": constraint.name,
            }
        )
    return serialized


def search_counterexample(
    scenario,
    guards: Iterable[Constraint],
    max_states: int,
):
    """Return ``(PASS|FAIL|UNKNOWN, counterexample, reason)``."""
    try:
        counterexample = shortest_counterexample(
            scenario.model,
            scenario.policy,
            guards,
            scenario.initial_state,
            max_states=max_states,
        )
    except SearchLimitExceeded as error:
        return "UNKNOWN", None, str(error)

    if counterexample is None:
        return "PASS", None, None
    return "FAIL", counterexample, None


def compute_domain_snapshot(scenario, max_states: int) -> dict:
    """Compute the guard-independent event domain once per scenario."""
    try:
        events, dangerous = compute_unconstrained_domains(
            scenario.model,
            scenario.policy,
            scenario.initial_state,
            max_states=max_states,
        )
    except SearchLimitExceeded as error:
        return {
            "status": "UNKNOWN",
            "error": str(error),
            "events": None,
            "dangerous": None,
        }
    return {
        "status": "AVAILABLE",
        "error": None,
        "events": events,
        "dangerous": dangerous,
    }


def eval_guards(
    scenario,
    guards,
    max_states=20000,
    domain_snapshot: Optional[dict] = None,
):
    """Evaluate guards without converting incomplete searches into PASS values."""
    guards = tuple(guards)
    verification_status, counterexample, verification_error = (
        search_counterexample(scenario, guards, max_states)
    )

    result = {
        "verification_status": verification_status,
        "verified": {
            "PASS": True,
            "FAIL": False,
            "UNKNOWN": None,
        }[verification_status],
        "verification_error": verification_error,
        "verification_counterexample": (
            counterexample_to_llm_json(counterexample)
            if counterexample is not None
            else None
        ),
        "domain_status": "AVAILABLE",
        "domain_error": None,
        "der": None,
        "bbr": None,
        "residual_dangerous": None,
        "total_dangerous": None,
        "total_benign": None,
        "unsafe_reach_status": "AVAILABLE",
        "unsafe_reach_error": None,
        "unsafe_reach": None,
        "max_states": max_states,
    }

    if domain_snapshot is None:
        domain_snapshot = compute_domain_snapshot(scenario, max_states)

    if domain_snapshot["status"] == "UNKNOWN":
        result["domain_status"] = "UNKNOWN"
        result["domain_error"] = domain_snapshot["error"]
    else:
        events = domain_snapshot["events"]
        dangerous = domain_snapshot["dangerous"]
        metrics = evaluate_constraints(guards, events, dangerous)
        result.update(
            {
                "der": metrics["DER"],
                "bbr": metrics["BBR"],
                "residual_dangerous": metrics["Residual"],
                "total_dangerous": metrics["Total_D"],
                "total_benign": metrics["Total_Benign"],
            }
        )

    if verification_status == "UNKNOWN":
        result["unsafe_reach_status"] = "UNKNOWN"
        result["unsafe_reach_error"] = verification_error
    else:
        try:
            result["unsafe_reach"] = unsafe_reachable_states(
                scenario.model,
                scenario.policy,
                scenario.initial_state,
                guards,
                max_states=max_states,
            )
        except SearchLimitExceeded as error:
            result["unsafe_reach_status"] = "UNKNOWN"
            result["unsafe_reach_error"] = str(error)

    return result


def run_m5(scenario, c0_guards, max_rounds=10, max_states=20000):
    """Run deterministic additive repair and report why the loop terminated."""
    constraints = list(c0_guards) if c0_guards else []

    for round_index in range(max_rounds):
        status, counterexample, _ = search_counterexample(
            scenario, constraints, max_states
        )
        if status == "PASS":
            return constraints, round_index, "PASS"
        if status == "UNKNOWN":
            return constraints, round_index, "UNKNOWN"
        if counterexample is None or counterexample.last_event is None:
            return constraints, round_index, "INITIAL_STATE_UNSAFE"

        last_event = counterexample.last_event
        forbidden_labels = forbidden_targets_of_action(
            scenario.policy, last_event.action
        )
        constraints.append(
            Constraint(
                agent=last_event.action.agent,
                tool=last_event.action.tool,
                param_filter=ParamFilter(
                    exact_patterns=(last_event.action.params_items,)
                ),
                forbidden_labels=forbidden_labels,
                name=f"auto_r{round_index}",
            )
        )
        constraints = list(semantic_normalize(constraints))

    status, _, _ = search_counterexample(scenario, constraints, max_states)
    return constraints, max_rounds, status if status != "FAIL" else "MAX_ROUNDS"


def format_rate(value) -> str:
    return "NA" if value is None else f"{value:.0%}"


def print_method_result(method: str, evaluation: dict, **details) -> None:
    suffix = " ".join(f"{key}={value}" for key, value in details.items())
    print(
        f"    {method}: {evaluation['verification_status']} "
        f"DER={format_rate(evaluation['der'])} "
        f"BBR={format_rate(evaluation['bbr'])} {suffix}".rstrip()
    )


def capture_llm_response(client, candidate_json) -> dict:
    """Capture one paid response before a later call overwrites client state."""
    return {
        "raw": client.last_raw_content,
        "parsed_json": candidate_json,
        "json_parse_error": client.last_parse_error,
        "candidate_format_error": None,
        "finish_reason": getattr(client, "last_finish_reason", None),
    }


def make_result(
    method: str,
    repetition: int,
    rounds: int,
    llm_calls: int,
    repair_llm_calls: int,
    total_tokens: int,
    cache_hit_tokens: int,
    total_time: float,
    repair_time: float,
    guards,
    candidate_json,
    evaluation: dict,
    repair_termination: Optional[str] = None,
    candidate_raw: Optional[str] = None,
    candidate_parse_status: Optional[str] = None,
    candidate_parse_error: Optional[str] = None,
    rejected_candidate_json=None,
    rejected_candidate_raw: Optional[str] = None,
    rejected_candidate_parse_error: Optional[str] = None,
    llm_responses: Optional[Sequence[dict]] = None,
) -> dict:
    return {
        "method": method,
        "repetition": repetition,
        "rounds": rounds,
        "llm_calls": llm_calls,
        "repair_llm_calls": repair_llm_calls,
        "total_tokens": total_tokens,
        "cache_hit_tokens": cache_hit_tokens,
        "time_s": round(total_time, 3),
        "repair_time_s": round(repair_time, 3),
        "repair_termination": repair_termination,
        "candidate_json": candidate_json,
        "candidate_raw": candidate_raw,
        "candidate_parse_status": candidate_parse_status,
        "candidate_parse_error": candidate_parse_error,
        "rejected_candidate_json": rejected_candidate_json,
        "rejected_candidate_raw": rejected_candidate_raw,
        "rejected_candidate_parse_error": rejected_candidate_parse_error,
        "llm_responses": list(llm_responses or ()),
        "guard_count": len(guards),
        "guards": constraints_to_json(guards),
        **evaluation,
    }


def run_rep(
    scenario_dir,
    rep,
    client,
    config,
    max_rounds=5,
    max_states=20000,
    domain_snapshot: Optional[dict] = None,
):
    scenario, description, spec = load_scenario(scenario_dir)
    scenario_name = Path(scenario_dir).name
    tools_schema = build_tools_schema(scenario, config)
    policy_schema = {
        str(location): sorted(labels)
        for location, labels in spec["policy"].items()
    }
    system_prompt = build_system_prompt(
        description, tools_schema, policy_schema
    )
    prompt_sha256 = hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()
    messages_base = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": build_initial_user_prompt()},
    ]

    shared_metadata = {
        "scenario": scenario_name,
        "config": config,
        "config_name": CONFIG_METADATA[config]["name"],
        "tool_schema_fields": CONFIG_METADATA[config]["tool_schema_fields"],
        "model": client.model,
        "temperature": LLM_TEMPERATURE,
        "max_output_tokens": LLM_MAX_TOKENS,
        "system_prompt_sha256": prompt_sha256,
    }

    results = []
    if domain_snapshot is None:
        domain_snapshot = compute_domain_snapshot(scenario, max_states)
    evaluation_cache = {}

    def evaluate(guards):
        key = tuple(guards)
        if key not in evaluation_cache:
            evaluation_cache[key] = eval_guards(
                scenario,
                guards,
                max_states=max_states,
                domain_snapshot=domain_snapshot,
            )
        return evaluation_cache[key]

    client.reset_stats()
    generation_started = time.time()
    c0_json = client.chat(
        messages_base,
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
    )
    generation_time = time.time() - generation_started
    generation_tokens = client.total_tokens
    generation_cache_tokens = client.cache_hit_tokens
    c0_raw = client.last_raw_content
    c0_response = capture_llm_response(client, c0_json)
    c0_parse_error = None
    try:
        if c0_json is None:
            raise CandidateFormatError(
                client.last_parse_error or "LLM returned no parseable candidate"
            )
        c0_guards = llm_json_to_constraints(c0_json)
        c0_parse_status = "VALID"
    except CandidateFormatError as error:
        # A malformed draft is an experimental outcome, not a missing row.
        # Treat it as the empty (allow-all) guard set so all repair methods can
        # still be evaluated under the same protocol.
        c0_guards = []
        c0_parse_status = "INVALID"
        c0_parse_error = str(error)
        c0_response["candidate_format_error"] = c0_parse_error
    c0_message = c0_raw or json.dumps(c0_json, separators=(",", ":"))

    m1_evaluation = evaluate(c0_guards)
    results.append(
        make_result(
            "M1",
            rep,
            rounds=0,
            llm_calls=1,
            repair_llm_calls=0,
            total_tokens=generation_tokens,
            cache_hit_tokens=generation_cache_tokens,
            total_time=generation_time,
            repair_time=0.0,
            guards=c0_guards,
            candidate_json=c0_json,
            candidate_raw=c0_raw,
            candidate_parse_status=c0_parse_status,
            candidate_parse_error=c0_parse_error,
            llm_responses=[c0_response],
            evaluation=m1_evaluation,
        )
    )
    print_method_result(
        "M1", m1_evaluation, tokens=generation_tokens,
        time=f"{generation_time:.1f}s"
    )

    client.reset_stats()
    repair_started = time.time()
    m2_messages = messages_base + [
        {"role": "assistant", "content": c0_message}
    ]
    m2_guards = list(c0_guards)
    m2_json = c0_json
    m2_raw = c0_raw
    m2_rejected_json = None
    m2_rejected_raw = None
    m2_parse_error = None
    m2_parse_status = c0_parse_status
    m2_responses = [c0_response]
    m2_rounds = 0
    m2_termination = "MAX_ROUNDS"

    for round_index in range(1, max_rounds + 1):
        if round_index == 1 and m1_evaluation["verification_status"] in (
            "PASS",
            "UNKNOWN",
        ):
            m2_termination = m1_evaluation["verification_status"]
            break
        status, counterexample, _ = search_counterexample(
            scenario, m2_guards, max_states
        )
        if status == "PASS":
            m2_termination = "PASS"
            break
        if status == "UNKNOWN":
            m2_termination = "UNKNOWN"
            break
        if counterexample is None or counterexample.last_event is None:
            m2_termination = "INITIAL_STATE_UNSAFE"
            break

        m2_rounds = round_index
        m2_messages.append(
            {"role": "user", "content": build_self_review_user_prompt()}
        )
        new_json = client.chat(
            m2_messages,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
        )
        new_raw = client.last_raw_content
        new_response = capture_llm_response(client, new_json)
        m2_responses.append(new_response)
        if new_json is None:
            m2_termination = "LLM_OUTPUT_ERROR"
            m2_rejected_raw = new_raw
            m2_parse_error = client.last_parse_error
            break
        try:
            new_guards = llm_json_to_constraints(new_json)
        except CandidateFormatError as error:
            new_response["candidate_format_error"] = str(error)
            m2_termination = "CANDIDATE_FORMAT_ERROR"
            m2_rejected_json = new_json
            m2_rejected_raw = new_raw
            m2_parse_error = str(error)
            break
        m2_messages.append(
            {
                "role": "assistant",
                "content": json.dumps(new_json, separators=(",", ":")),
            }
        )
        m2_json = new_json
        m2_raw = new_raw
        m2_guards = new_guards
        m2_parse_status = "VALID"

    m2_repair_time = time.time() - repair_started
    m2_evaluation = evaluate(m2_guards)
    if (
        m2_termination == "MAX_ROUNDS"
        and m2_evaluation["verification_status"] == "PASS"
    ):
        m2_termination = "PASS"
    results.append(
        make_result(
            "M2",
            rep,
            rounds=m2_rounds,
            llm_calls=1 + m2_rounds,
            repair_llm_calls=m2_rounds,
            total_tokens=generation_tokens + client.total_tokens,
            cache_hit_tokens=(generation_cache_tokens + client.cache_hit_tokens),
            total_time=generation_time + m2_repair_time,
            repair_time=m2_repair_time,
            guards=m2_guards,
            candidate_json=m2_json,
            candidate_raw=m2_raw,
            candidate_parse_status=m2_parse_status,
            candidate_parse_error=(
                c0_parse_error if m2_parse_status == "INVALID" else None
            ),
            rejected_candidate_json=m2_rejected_json,
            rejected_candidate_raw=m2_rejected_raw,
            rejected_candidate_parse_error=m2_parse_error,
            llm_responses=m2_responses,
            evaluation=m2_evaluation,
            repair_termination=m2_termination,
        )
    )
    print_method_result(
        "M2", m2_evaluation, rounds=m2_rounds,
        repair_time=f"{m2_repair_time:.1f}s"
    )

    client.reset_stats()
    repair_started = time.time()
    m3_messages = messages_base + [
        {"role": "assistant", "content": c0_message}
    ]
    m3_guards = list(c0_guards)
    m3_json = c0_json
    m3_raw = c0_raw
    m3_rejected_json = None
    m3_rejected_raw = None
    m3_parse_error = None
    m3_parse_status = c0_parse_status
    m3_responses = [c0_response]
    m3_rounds = 0
    m3_termination = "MAX_ROUNDS"

    for round_index in range(1, max_rounds + 1):
        if round_index == 1 and m1_evaluation["verification_status"] in (
            "PASS",
            "UNKNOWN",
        ):
            m3_termination = m1_evaluation["verification_status"]
            break
        status, counterexample, _ = search_counterexample(
            scenario, m3_guards, max_states
        )
        if status == "PASS":
            m3_termination = "PASS"
            break
        if status == "UNKNOWN":
            m3_termination = "UNKNOWN"
            break
        if counterexample is None or counterexample.last_event is None:
            m3_termination = "INITIAL_STATE_UNSAFE"
            break

        m3_rounds = round_index
        m3_messages.append(
            {
                "role": "user",
                "content": build_verdict_only_user_prompt(
                    violating_count=1
                ),
            }
        )
        new_json = client.chat(
            m3_messages,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
        )
        new_raw = client.last_raw_content
        new_response = capture_llm_response(client, new_json)
        m3_responses.append(new_response)
        if new_json is None:
            m3_termination = "LLM_OUTPUT_ERROR"
            m3_rejected_raw = new_raw
            m3_parse_error = client.last_parse_error
            break
        try:
            new_guards = llm_json_to_constraints(new_json)
        except CandidateFormatError as error:
            new_response["candidate_format_error"] = str(error)
            m3_termination = "CANDIDATE_FORMAT_ERROR"
            m3_rejected_json = new_json
            m3_rejected_raw = new_raw
            m3_parse_error = str(error)
            break
        m3_messages.append(
            {
                "role": "assistant",
                "content": json.dumps(new_json, separators=(",", ":")),
            }
        )
        m3_json = new_json
        m3_raw = new_raw
        m3_guards = new_guards
        m3_parse_status = "VALID"

    m3_repair_time = time.time() - repair_started
    m3_evaluation = evaluate(m3_guards)
    if (
        m3_termination == "MAX_ROUNDS"
        and m3_evaluation["verification_status"] == "PASS"
    ):
        m3_termination = "PASS"
    results.append(
        make_result(
            "M3",
            rep,
            rounds=m3_rounds,
            llm_calls=1 + m3_rounds,
            repair_llm_calls=m3_rounds,
            total_tokens=generation_tokens + client.total_tokens,
            cache_hit_tokens=(generation_cache_tokens + client.cache_hit_tokens),
            total_time=generation_time + m3_repair_time,
            repair_time=m3_repair_time,
            guards=m3_guards,
            candidate_json=m3_json,
            candidate_raw=m3_raw,
            candidate_parse_status=m3_parse_status,
            candidate_parse_error=(
                c0_parse_error if m3_parse_status == "INVALID" else None
            ),
            rejected_candidate_json=m3_rejected_json,
            rejected_candidate_raw=m3_rejected_raw,
            rejected_candidate_parse_error=m3_parse_error,
            llm_responses=m3_responses,
            evaluation=m3_evaluation,
            repair_termination=m3_termination,
        )
    )
    print_method_result(
        "M3", m3_evaluation, rounds=m3_rounds,
        repair_time=f"{m3_repair_time:.1f}s"
    )

    client.reset_stats()
    repair_started = time.time()
    m4_messages = messages_base + [
        {"role": "assistant", "content": c0_message}
    ]
    m4_guards = list(c0_guards)
    m4_json = c0_json
    m4_raw = c0_raw
    m4_rejected_json = None
    m4_rejected_raw = None
    m4_parse_error = None
    m4_parse_status = c0_parse_status
    m4_responses = [c0_response]
    m4_rounds = 0
    m4_termination = "MAX_ROUNDS"

    for round_index in range(1, max_rounds + 1):
        if round_index == 1 and m1_evaluation["verification_status"] in (
            "PASS",
            "UNKNOWN",
        ):
            m4_termination = m1_evaluation["verification_status"]
            break
        status, counterexample, _ = search_counterexample(
            scenario, m4_guards, max_states
        )
        if status == "PASS":
            m4_termination = "PASS"
            break
        if status == "UNKNOWN":
            m4_termination = "UNKNOWN"
            break
        if counterexample is None or counterexample.last_event is None:
            m4_termination = "INITIAL_STATE_UNSAFE"
            break

        m4_rounds = round_index
        feedback = counterexample_to_llm_json(counterexample)
        m4_messages.append(
            {
                "role": "user",
                "content": build_counterexample_user_prompt(
                    feedback, m4_json or []
                ),
            }
        )
        new_json = client.chat(
            m4_messages,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
        )
        new_raw = client.last_raw_content
        new_response = capture_llm_response(client, new_json)
        m4_responses.append(new_response)
        if new_json is None:
            m4_termination = "LLM_OUTPUT_ERROR"
            m4_rejected_raw = new_raw
            m4_parse_error = client.last_parse_error
            break
        try:
            new_guards = llm_json_to_constraints(new_json)
        except CandidateFormatError as error:
            new_response["candidate_format_error"] = str(error)
            m4_termination = "CANDIDATE_FORMAT_ERROR"
            m4_rejected_json = new_json
            m4_rejected_raw = new_raw
            m4_parse_error = str(error)
            break
        m4_messages.append(
            {
                "role": "assistant",
                "content": json.dumps(new_json, separators=(",", ":")),
            }
        )
        m4_json = new_json
        m4_raw = new_raw
        m4_guards = new_guards
        m4_parse_status = "VALID"

    m4_repair_time = time.time() - repair_started
    m4_evaluation = evaluate(m4_guards)
    if (
        m4_termination == "MAX_ROUNDS"
        and m4_evaluation["verification_status"] == "PASS"
    ):
        m4_termination = "PASS"
    results.append(
        make_result(
            "M4",
            rep,
            rounds=m4_rounds,
            llm_calls=1 + m4_rounds,
            repair_llm_calls=m4_rounds,
            total_tokens=generation_tokens + client.total_tokens,
            cache_hit_tokens=(generation_cache_tokens + client.cache_hit_tokens),
            total_time=generation_time + m4_repair_time,
            repair_time=m4_repair_time,
            guards=m4_guards,
            candidate_json=m4_json,
            candidate_raw=m4_raw,
            candidate_parse_status=m4_parse_status,
            candidate_parse_error=(
                c0_parse_error if m4_parse_status == "INVALID" else None
            ),
            rejected_candidate_json=m4_rejected_json,
            rejected_candidate_raw=m4_rejected_raw,
            rejected_candidate_parse_error=m4_parse_error,
            llm_responses=m4_responses,
            evaluation=m4_evaluation,
            repair_termination=m4_termination,
        )
    )
    print_method_result(
        "M4", m4_evaluation, rounds=m4_rounds,
        repair_time=f"{m4_repair_time:.1f}s"
    )

    repair_started = time.time()
    if m1_evaluation["verification_status"] in ("PASS", "UNKNOWN"):
        m5_guards = list(c0_guards)
        m5_rounds = 0
        m5_termination = m1_evaluation["verification_status"]
    else:
        m5_guards, m5_rounds, m5_termination = run_m5(
            scenario,
            c0_guards,
            max_rounds=10,
            max_states=max_states,
        )
    m5_repair_time = time.time() - repair_started
    m5_evaluation = evaluate(m5_guards)
    results.append(
        make_result(
            "M5",
            rep,
            rounds=m5_rounds,
            llm_calls=1,
            repair_llm_calls=0,
            total_tokens=generation_tokens,
            cache_hit_tokens=generation_cache_tokens,
            total_time=generation_time + m5_repair_time,
            repair_time=m5_repair_time,
            guards=m5_guards,
            candidate_json=constraints_to_json(m5_guards),
            llm_responses=[c0_response],
            evaluation=m5_evaluation,
            repair_termination=m5_termination,
        )
    )
    print_method_result(
        "M5", m5_evaluation, rounds=m5_rounds,
        repair_time=f"{m5_repair_time:.3f}s"
    )

    synthesis_started = time.time()
    m6_guards = direct_sage(scenario.model, scenario.policy)
    m6_time = time.time() - synthesis_started
    m6_evaluation = evaluate(m6_guards)
    results.append(
        make_result(
            "M6",
            rep,
            rounds=0,
            llm_calls=0,
            repair_llm_calls=0,
            total_tokens=0,
            cache_hit_tokens=0,
            total_time=m6_time,
            repair_time=0.0,
            guards=m6_guards,
            candidate_json=constraints_to_json(m6_guards),
            evaluation=m6_evaluation,
        )
    )
    print_method_result("M6", m6_evaluation, time=f"{m6_time:.3f}s")

    for result in results:
        result.update(shared_metadata)

    prompt_record = {
        "scenario": scenario_name,
        "config": config,
        "system_prompt_sha256": prompt_sha256,
        "system_prompt": system_prompt,
        "tool_schema": tools_schema,
    }
    return results, prompt_record


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with open(temporary, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)
    temporary.replace(path)


def default_output_path(config: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(
        f"experiments/reports/llm_batch_config_{config.lower()}_{timestamp}.json"
    )


def print_summary(results: Sequence[dict]) -> None:
    print(
        f"{'Method':<7} {'PASS':<8} {'FAIL':<8} {'UNKNOWN':<9} "
        f"{'Med rounds':<11} {'Med DER':<9} {'Med BBR':<9}"
    )
    print("-" * 72)

    for method in ("M1", "M2", "M3", "M4", "M5", "M6"):
        method_results = [r for r in results if r["method"] == method]
        if not method_results:
            continue
        counts = {
            status: sum(
                r["verification_status"] == status for r in method_results
            )
            for status in ("PASS", "FAIL", "UNKNOWN")
        }
        median_rounds = statistics.median(r["rounds"] for r in method_results)
        known_der = [r["der"] for r in method_results if r["der"] is not None]
        known_bbr = [r["bbr"] for r in method_results if r["bbr"] is not None]
        median_der = statistics.median(known_der) if known_der else None
        median_bbr = statistics.median(known_bbr) if known_bbr else None
        print(
            f"{method:<7} {counts['PASS']:<8} {counts['FAIL']:<8} "
            f"{counts['UNKNOWN']:<9} {median_rounds:<11} "
            f"{format_rate(median_der):<9} {format_rate(median_bbr):<9}"
        )


def preflight_scenarios(scenario_dirs, max_states: int) -> bool:
    """Check that metric ground-truth domains fit before any paid LLM call."""
    all_available = True
    print(f"Preflight only: max_states={max_states}; no LLM client is created.")

    for scenario_dir in scenario_dirs:
        scenario_name = Path(scenario_dir).name
        scenario, _, _ = load_scenario(scenario_dir)
        started = time.time()
        try:
            events, dangerous = compute_unconstrained_domains(
                scenario.model,
                scenario.policy,
                scenario.initial_state,
                max_states=max_states,
            )
        except SearchLimitExceeded as error:
            all_available = False
            print(
                f"  {scenario_name}: UNKNOWN ({error}) "
                f"after {time.time() - started:.2f}s"
            )
        else:
            print(
                f"  {scenario_name}: AVAILABLE events={len(events)} "
                f"dangerous={len(dangerous)} "
                f"time={time.time() - started:.2f}s"
            )

    return all_available


def run_batch(
    scenario_dirs,
    config,
    repetitions=3,
    repetition_start=1,
    max_rounds=5,
    max_states=20000,
    model=DEFAULT_MODEL,
    output_path: Optional[Path] = None,
    include_unknown_domains: bool = False,
):
    config = config.upper()
    if config not in CONFIG_METADATA:
        raise ValueError(f"unsupported config: {config}")
    if repetitions < 1 or repetition_start < 1 or max_rounds < 1 or max_states < 1:
        raise ValueError(
            "repetitions, repetition_start, max_rounds, and max_states must be positive"
        )

    output = Path(output_path) if output_path else default_output_path(config)
    if output.exists():
        raise FileExistsError(
            f"refusing to overwrite existing experiment data: {output}"
        )

    # Import lazily so offline analysis and --help do not require the API SDK.
    from experiments.llm_client import SAGE_LLM_Client

    client = SAGE_LLM_Client(model=model)
    run_id = output.stem
    payload = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "run": {
            "run_id": run_id,
            "status": "RUNNING",
            "started_at_utc": utc_now(),
            "completed_at_utc": None,
            "config": config,
            "config_name": CONFIG_METADATA[config]["name"],
            "config_description": CONFIG_METADATA[config]["description"],
            "tool_schema_fields": CONFIG_METADATA[config]["tool_schema_fields"],
            "model": model,
            "temperature": LLM_TEMPERATURE,
            "max_output_tokens": LLM_MAX_TOKENS,
            "repetitions": repetitions,
            "repetition_start": repetition_start,
            "max_rounds": max_rounds,
            "max_states": max_states,
            "scenarios": [str(path) for path in scenario_dirs],
        },
        "prompts": {},
        "domains": {},
        "results": [],
        "errors": [],
        "skipped_scenarios": [],
    }
    write_json_atomic(output, payload)

    print(
        f"Run {run_id}: Config {config}, model={model}, "
        f"max_states={max_states}"
    )

    for scenario_dir in scenario_dirs:
        scenario_name = Path(scenario_dir).name
        print(f"\nScenario: {scenario_name}")
        scenario, _, _ = load_scenario(scenario_dir)
        domain_started = time.time()
        domain_snapshot = compute_domain_snapshot(scenario, max_states)
        domain_record = {
            "status": domain_snapshot["status"],
            "error": domain_snapshot["error"],
            "events": (
                len(domain_snapshot["events"])
                if domain_snapshot["events"] is not None
                else None
            ),
            "dangerous": (
                len(domain_snapshot["dangerous"])
                if domain_snapshot["dangerous"] is not None
                else None
            ),
            "time_s": round(time.time() - domain_started, 3),
        }
        payload["domains"][scenario_name] = domain_record
        write_json_atomic(output, payload)

        if (
            domain_snapshot["status"] == "UNKNOWN"
            and not include_unknown_domains
        ):
            payload["skipped_scenarios"].append(
                {
                    "scenario": scenario_name,
                    "reason": "UNCONSTRAINED_DOMAIN_UNKNOWN",
                    "detail": domain_snapshot["error"],
                }
            )
            print(
                "  SKIPPED: unconstrained event domain is UNKNOWN; "
                "no paid LLM call was made."
            )
            write_json_atomic(output, payload)
            continue

        for repetition in range(repetition_start, repetition_start + repetitions):
            print(
                f"  Repetition {repetition} "
                f"({repetition - repetition_start + 1}/{repetitions} in this run)"
            )
            try:
                rep_results, prompt_record = run_rep(
                    scenario_dir,
                    repetition,
                    client,
                    config,
                    max_rounds=max_rounds,
                    max_states=max_states,
                    domain_snapshot=domain_snapshot,
                )
            except Exception as error:
                error_record = {
                    "scenario": scenario_name,
                    "repetition": repetition,
                    "config": config,
                    "error_type": type(error).__name__,
                    "message": str(error),
                    "recorded_at_utc": utc_now(),
                }
                if isinstance(error, CandidateFormatError):
                    error_record.update(
                        {
                            "candidate_json": error.candidate_json,
                            "candidate_raw": client.last_raw_content,
                            "candidate_parse_error": str(error),
                        }
                    )
                payload["errors"].append(error_record)
                print(
                    f"  ERROR: {type(error).__name__}: {error}. "
                    "The failure was recorded."
                )
            else:
                payload["results"].extend(rep_results)
                payload["prompts"][scenario_name] = prompt_record

            # Preserve paid calls even if a later scenario or repetition fails.
            write_json_atomic(output, payload)

    payload["run"]["status"] = (
        "COMPLETED_WITH_ERRORS" if payload["errors"] else "COMPLETED"
    )
    payload["run"]["completed_at_utc"] = utc_now()
    write_json_atomic(output, payload)

    print_summary(payload["results"])
    print(f"\nSaved: {output}")
    return output


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        required=True,
        choices=("A", "C", "a", "c"),
        help="A omits structured data-flow fields; C includes reads/writes/gen.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument(
        "--repetition-start",
        type=int,
        default=1,
        help="First repetition identifier; use 4 to append repetitions 4 and 5.",
    )
    parser.add_argument("--max-rounds", type=int, default=5)
    parser.add_argument("--max-states", type=int, default=20000)
    parser.add_argument(
        "--scenarios",
        nargs="+",
        default=list(DEFAULT_SCENARIOS),
        help="Scenario directories. Defaults to s1_full through s9_full.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output JSON path. Existing files are never overwritten.",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help=(
            "Check state-domain limits without importing the API client or "
            "calling an LLM."
        ),
    )
    parser.add_argument(
        "--include-unknown-domains",
        action="store_true",
        help=(
            "Run paid LLM calls even when preflight cannot enumerate the "
            "event domain. DER and BBR will be unavailable."
        ),
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.preflight_only:
        preflight_scenarios(args.scenarios, args.max_states)
        return

    run_batch(
        scenario_dirs=args.scenarios,
        config=args.config.upper(),
        repetitions=args.repetitions,
        repetition_start=args.repetition_start,
        max_rounds=args.max_rounds,
        max_states=args.max_states,
        model=args.model,
        output_path=args.output,
        include_unknown_domains=args.include_unknown_domains,
    )


if __name__ == "__main__":
    main()
