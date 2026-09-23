"""
@function      :
@time          :2026/8/3 15:40
"""
# sage/v2/tests/test_scenario_input.py

from __future__ import annotations

import pytest

from sage.v2.counterexample import shortest_counterexample, trace_safe
from sage.v2.model import Location
from sage.v2.scenario import build_scenario, parse_location
from sage.v2.synthesis import direct_sage


def test_parse_location():
    ctx = parse_location("ctx:support")
    assert ctx == Location.ctx("support")

    slot_no_slot = parse_location("slot:file")
    assert slot_no_slot == Location.slot("file")

    slot_with_slot = parse_location("slot:file.T1")
    assert slot_with_slot == Location.slot("file", "T1")

    with pytest.raises(ValueError):
        parse_location("invalid_location")


def test_scenario_build_minimal_leak():
    spec = {
        "agents": ["support"],
        "tools": ["send_file"],
        "labels": ["PII"],
        "actions": [
            {
                "agent": "support",
                "tool": "send_file",
                "params": {
                    "file": "T1",
                    "channel": "external",
                },
                "reads": [
                    "ctx:support",
                    "slot:file.T1",
                ],
                "writes": [
                    "slot:external.slack",
                ],
                "gen": [],
            }
        ],
        "policy": {
            "slot:external.slack": ["PII"],
        },
        "initial_state": {
            "slot:file.T1": ["PII"],
        },
    }

    scenario = build_scenario(spec)

    # 无约束时应有反例
    cex = shortest_counterexample(
        model=scenario.model,
        policy=scenario.policy,
        constraints=(),
        initial_state=scenario.initial_state,
    )
    assert cex is not None

    # DirectSAGE 应安全
    guards = direct_sage(scenario.model, scenario.policy)

    assert trace_safe(
        model=scenario.model,
        policy=scenario.policy,
        constraints=guards,
        initial_state=scenario.initial_state,
    )


def test_scenario_user_constraints_can_block_leak():
    spec = {
        "agents": ["support"],
        "tools": ["send_file"],
        "labels": ["PII"],
        "actions": [
            {
                "agent": "support",
                "tool": "send_file",
                "params": {
                    "file": "T1",
                    "channel": "external",
                },
                "reads": [
                    "ctx:support",
                    "slot:file.T1",
                ],
                "writes": [
                    "slot:external.slack",
                ],
                "gen": [],
            }
        ],
        "policy": {
            "slot:external.slack": ["PII"],
        },
        "initial_state": {
            "slot:file.T1": ["PII"],
        },
        "constraints": [
            {
                "name": "block_pii_external_send",
                "agent": "support",
                "tool": "send_file",
                "params": {
                    "file": "T1",
                    "channel": "external",
                },
                "forbidden_labels": ["PII"],
            }
        ],
    }

    scenario = build_scenario(spec)

    assert trace_safe(
        model=scenario.model,
        policy=scenario.policy,
        constraints=scenario.constraints,
        initial_state=scenario.initial_state,
    )


def test_scenario_missing_user_constraint_leaves_counterexample():
    spec = {
        "agents": ["support"],
        "tools": ["send_file"],
        "labels": ["PII"],
        "actions": [
            {
                "agent": "support",
                "tool": "send_file",
                "params": {
                    "file": "T1",
                    "channel": "external",
                },
                "reads": [
                    "ctx:support",
                    "slot:file.T1",
                ],
                "writes": [
                    "slot:external.slack",
                ],
                "gen": [],
            }
        ],
        "policy": {
            "slot:external.slack": ["PII"],
        },
        "initial_state": {
            "slot:file.T1": ["PII"],
        },
        "constraints": [],
    }

    scenario = build_scenario(spec)

    cex = shortest_counterexample(
        model=scenario.model,
        policy=scenario.policy,
        constraints=scenario.constraints,
        initial_state=scenario.initial_state,
    )

    assert cex is not None


def test_scenario_constraint_requires_explicit_param_policy():
    spec = {
        "agents": ["support"],
        "tools": ["send_file"],
        "labels": ["PII"],
        "actions": [
            {
                "agent": "support",
                "tool": "send_file",
                "params": {
                    "file": "T1",
                    "channel": "external",
                },
                "reads": [
                    "ctx:support",
                    "slot:file.T1",
                ],
                "writes": [
                    "slot:external.slack",
                ],
                "gen": [],
            }
        ],
        "policy": {
            "slot:external.slack": ["PII"],
        },
        "initial_state": {
            "slot:file.T1": ["PII"],
        },
        "constraints": [
            {
                "name": "bad_constraint_without_params",
                "agent": "support",
                "tool": "send_file",
                "forbidden_labels": ["PII"],
            }
        ],
    }

    with pytest.raises(ValueError):
        build_scenario(spec)
