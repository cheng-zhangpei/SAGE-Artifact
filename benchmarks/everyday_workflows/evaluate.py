"""Strict candidate parsing and separate event/trace diagnostics."""

import json

from experiments.run_llm_batch import CandidateFormatError, llm_json_to_constraints, search_counterexample
from sage.v2.counterexample import counterexample_to_llm_json
from sage.v2.guards import deny_constraints
from sage.v2.scenario import build_scenario
from sage.v2.semantics import execute
from sage.v2.synthesis import direct_sage

from .dataset import scenario_spec


def reject_constant(value):
    raise ValueError(f"Non-JSON constant: {value}")


def unique_object(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json(text):
    return json.loads(text, parse_constant=reject_constant, object_pairs_hook=unique_object)


def call_signature(agent, tool, params):
    return json.dumps([agent, tool, params], sort_keys=True, ensure_ascii=False, allow_nan=False)


def parse_candidate(workflow, raw):
    candidate = strict_json(raw)
    guards = llm_json_to_constraints(candidate)
    calls = {
        call_signature(action["agent"], action["tool"], action["params"])
        for action in workflow["actions"]
    }
    for clause in candidate["guards"]:
        signature = call_signature(clause["agent"], clause["tool"], clause["params"])
        if signature not in calls:
            raise CandidateFormatError("Guard does not match an available concrete call")
        if set(clause["forbidden_labels"]) - set(workflow["labels"]):
            raise CandidateFormatError("Guard contains undeclared labels")
    return guards


def evaluate_guards(workflow, guards, max_states=20000):
    scenario = build_scenario(scenario_spec(workflow))
    status, counterexample, reason = search_counterexample(scenario, guards, max_states)
    actions = dict(zip((action["id"] for action in workflow["actions"]), scenario.model.actions))
    probes = []
    correct_pairs = 0
    for pair in workflow["pairs"]:
        pair_correct = True
        for kind in ("danger", "benign"):
            probe = pair[kind]
            state = scenario.initial_state
            blocked_prefix = []
            for action_id in probe["prefix"]:
                action = actions[action_id]
                if deny_constraints(guards, state, action):
                    blocked_prefix.append(action_id)
                state = execute(state, action)
            denied = deny_constraints(guards, state, actions[probe["target"]])
            correct = denied == (kind == "danger")
            pair_correct = pair_correct and correct
            probes.append({
                "pair": pair["id"], "class": kind, "target": probe["target"],
                "expected": "DENY" if kind == "danger" else "ALLOW",
                "decision": "DENY" if denied else "ALLOW", "correct": correct,
                "blocked_prefix_actions": blocked_prefix,
                "reachable_along_this_prefix": not blocked_prefix,
            })
        correct_pairs += int(pair_correct)
    dangerous = [probe for probe in probes if probe["class"] == "danger"]
    benign = [probe for probe in probes if probe["class"] == "benign"]
    return {
        "verification_status": status,
        "verification_error": reason,
        "counterexample": counterexample_to_llm_json(counterexample) if counterexample else None,
        "probe_der": sum(probe["decision"] == "DENY" for probe in dangerous) / len(dangerous),
        "probe_bbr": sum(probe["decision"] == "DENY" for probe in benign) / len(benign),
        "correct_pairs": correct_pairs, "total_pairs": len(workflow["pairs"]),
        "benign_prefix_blocked": sum(bool(probe["blocked_prefix_actions"]) for probe in benign),
        "probe_domain": "fixed handwritten probes, independent of candidate reachability",
        "probes": probes,
    }


def evaluate_candidate(workflow, raw, max_states=20000):
    try:
        guards = parse_candidate(workflow, raw)
    except (ValueError, TypeError) as error:
        return {"candidate_status": "FORMAT_ERROR", "error": str(error),
                "verification_status": "NOT_RUN"}
    return {"candidate_status": "VALID", **evaluate_guards(workflow, guards, max_states)}


def evaluate_direct(workflow, max_states=20000):
    scenario = build_scenario(scenario_spec(workflow))
    guards = direct_sage(scenario.model, scenario.policy)
    return evaluate_guards(workflow, guards, max_states)
