"""Offline data validation, not an LLM experiment or a physical replay."""

import json

from sage.v2.counterexample import shortest_counterexample
from sage.v2.guards import deny_constraints
from sage.v2.scenario import build_scenario
from sage.v2.semantics import execute, is_safe
from sage.v2.synthesis import direct_sage

from .dataset import drafting_input, load_boundaries, load_implicit_cases, load_workflows, scenario_spec


def check(condition, message):
    if not condition:
        raise ValueError(message)


def validate():
    rows = []
    identifiers = set()
    for workflow in load_workflows():
        identity = workflow["id"]
        check(identity not in identifiers, f"Duplicate workflow: {identity}")
        identifiers.add(identity)
        spec = scenario_spec(workflow)
        scenario = build_scenario(spec)
        actions = dict(zip((action["id"] for action in workflow["actions"]), scenario.model.actions))
        check(len(actions) == len(workflow["actions"]), f"{identity}: duplicate action IDs")
        signatures = {(action.agent, action.tool, action.params_items) for action in actions.values()}
        check(len(signatures) == len(actions), f"{identity}: duplicate concrete calls")
        check(is_safe(scenario.initial_state, scenario.policy), f"{identity}: unsafe initial state")
        guards = direct_sage(scenario.model, scenario.policy)
        pair_ids = set()
        for pair in workflow["pairs"]:
            check(pair["id"] not in pair_ids, f"{identity}: duplicate pair")
            pair_ids.add(pair["id"])
            check(pair["danger"] != pair["benign"], f"{identity}: identical probes")
            for kind in ("danger", "benign"):
                probe = pair[kind]
                state = scenario.initial_state
                for action_id in probe["prefix"]:
                    action = actions[action_id]
                    check(not deny_constraints(guards, state, action), f"{identity}: blocked prefix")
                    state = execute(state, action)
                    check(is_safe(state, scenario.policy), f"{identity}: unsafe prefix")
                target = actions[probe["target"]]
                expected = kind == "danger"
                actual = not is_safe(execute(state, target), scenario.policy)
                check(actual == expected, f"{identity}/{pair['id']}/{kind}: incorrect oracle")
                check(deny_constraints(guards, state, target) == expected, f"{identity}: guard mismatch")
        public = drafting_input(workflow)
        check(set(public) == {"description", "labels", "tools", "policy"}, f"{identity}: prompt fields")
        for tool in public["tools"]:
            check(set(tool) == {"agent", "tool", "params", "description"}, f"{identity}: leaked semantics")
        counterexample = shortest_counterexample(
            scenario.model, scenario.policy, (), scenario.initial_state, max_states=20000
        )
        check(counterexample is not None, f"{identity}: no unguarded violation")
        guarded = shortest_counterexample(
            scenario.model, scenario.policy, guards, scenario.initial_state, max_states=20000
        )
        check(guarded is None, f"{identity}: compiled guards unsafe")
        rows.append({"id": identity, "pairs": len(pair_ids), "actions": len(actions),
                     "unguarded_shortest_trace": len(counterexample.trace), "compiled_verdict": "PASS"})
    boundaries = load_boundaries()
    for boundary in boundaries:
        check(boundary["id"] not in identifiers, "Duplicate boundary ID")
        identifiers.add(boundary["id"])
        check(len(boundary["probes"]) == 2, "Boundary must have two contrasting probes")
        check(bool(boundary["reason"]) and bool(boundary["required_extension"]), "Missing scope explanation")
    implicit = load_implicit_cases()
    for case in implicit:
        check(case["id"] not in identifiers, f"Duplicate implicit ID: {case['id']}")
        identifiers.add(case["id"])
        check(case["sage_assessment"] == "UNSUPPORTED_PROPERTY", f"{case['id']}: implicit case must be unsupported")
        check(case["business_expected"] == "DENY", f"{case['id']}: unexpected implicit oracle")
        check(case["secret"] and case["observable"] and case["reason"], f"{case['id']}: incomplete implicit case")
    return {"workflows": rows, "pairs": sum(row["pairs"] for row in rows),
            "boundary_cases": len(boundaries), "implicit_flow_cases": len(implicit),
            "boundary_execution": "NOT_IMPLEMENTED",
            "llm_experiment": "NOT_RUN", "physical_replay": "NOT_RUN"}


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False, indent=2))
