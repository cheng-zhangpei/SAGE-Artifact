"""
@function      :
@time          :2026/8/3 15:39
"""
# sage/v2/tests/test_counterexample.py

from __future__ import annotations

from types import SimpleNamespace

import pytest

from experiments.run_llm_batch import build_tools_schema, eval_guards
from sage.v2.counterexample import (
    SearchLimitExceeded,
    counterexample_to_llm_json,
    shortest_counterexample,
)
from sage.v2.model import (
    Location,
    ToolModel,
    make_action,
    make_policy,
    make_state,
)
from sage.v2.synthesis import direct_sage


def _build_two_step_leak_model():
    """
    构造两步泄露：

    1. copy: source -> shared；
    2. send: shared -> external。

    初始只有 source 带 PII。
    最短反例长度应为 2。
    """

    agent = "a"

    ctx = Location.ctx(agent)
    source = Location.slot("source", "s1")
    shared = Location.slot("shared", "log")
    external = Location.slot("external", "slack")

    copy = make_action(
        agent=agent,
        tool="copy",
        params={"src": "s1", "dst": "shared_log"},
        reads=[ctx, source],
        writes=[shared],
        gen=[],
    )

    send = make_action(
        agent=agent,
        tool="send",
        params={"src": "shared_log", "dst": "external"},
        reads=[ctx, shared],
        writes=[external],
        gen=[],
    )

    model = ToolModel(
        agents=frozenset({agent}),
        tools=frozenset({"copy", "send"}),
        locations=frozenset({ctx, source, shared, external}),
        labels=frozenset({"PII"}),
        actions=(copy, send),
    )

    policy = make_policy({external: {"PII"}})
    initial_state = make_state({source: {"PII"}})

    return model, policy, initial_state


def test_initial_bad_state_returns_initial_counterexample(minimal_leak):
    model, policy, _ = minimal_leak

    external = Location.slot("external", "slack")
    bad_initial_state = make_state({external: {"PII"}})

    cex = shortest_counterexample(
        model=model,
        policy=policy,
        constraints=(),
        initial_state=bad_initial_state,
    )

    assert cex is not None
    assert cex.last_event is None
    assert cex.violations
    assert cex.violations[0][0] == "PII"


def test_shortest_counterexample_one_step(minimal_leak):
    model, policy, initial_state = minimal_leak

    cex = shortest_counterexample(
        model=model,
        policy=policy,
        constraints=(),
        initial_state=initial_state,
    )

    assert cex is not None
    assert len(cex.trace) == 1
    assert cex.last_event is not None
    assert cex.last_event.action.tool == "send_file"
    assert cex.violations[0][0] == "PII"


def test_shortest_counterexample_two_steps():
    model, policy, initial_state = _build_two_step_leak_model()

    cex = shortest_counterexample(
        model=model,
        policy=policy,
        constraints=(),
        initial_state=initial_state,
    )

    assert cex is not None
    assert len(cex.trace) == 2

    first_step, second_step = cex.trace

    assert first_step.action.tool == "copy"
    assert second_step.action.tool == "send"

    assert cex.last_event is not None
    assert cex.last_event.action.tool == "send"
    assert cex.violations[0][0] == "PII"


def test_direct_sage_removes_two_step_counterexample():
    model, policy, initial_state = _build_two_step_leak_model()

    guards = direct_sage(model, policy)

    cex = shortest_counterexample(
        model=model,
        policy=policy,
        constraints=guards,
        initial_state=initial_state,
    )

    assert cex is None


def test_search_limit_is_unknown_not_safe():
    model, policy, initial_state = _build_two_step_leak_model()

    with pytest.raises(SearchLimitExceeded):
        shortest_counterexample(
            model=model,
            policy=policy,
            constraints=(),
            initial_state=initial_state,
            max_states=1,
        )


def test_experiment_evaluation_preserves_unknown_status():
    model, policy, initial_state = _build_two_step_leak_model()
    scenario = SimpleNamespace(
        model=model,
        policy=policy,
        initial_state=initial_state,
    )

    result = eval_guards(scenario, (), max_states=1)

    assert result["verification_status"] == "UNKNOWN"
    assert result["verified"] is None
    assert result["domain_status"] == "UNKNOWN"
    assert result["der"] is None
    assert result["bbr"] is None


def test_config_c_only_adds_structured_data_flow_fields():
    model, _, _ = _build_two_step_leak_model()
    scenario = SimpleNamespace(model=model)

    config_a = build_tools_schema(scenario, "A")
    config_c = build_tools_schema(scenario, "C")

    assert set(config_a[0]) == {"agent", "tool", "params"}
    assert set(config_c[0]) == {
        "agent",
        "tool",
        "params",
        "reads",
        "writes",
        "gen",
    }
    assert [
        {key: item[key] for key in ("agent", "tool", "params")}
        for item in config_c
    ] == config_a


def test_counterexample_llm_json_schema(minimal_leak):
    model, policy, initial_state = minimal_leak

    cex = shortest_counterexample(
        model=model,
        policy=policy,
        constraints=(),
        initial_state=initial_state,
    )

    assert cex is not None

    payload = counterexample_to_llm_json(cex)

    assert "violated_flow" in payload
    assert "trace" in payload
    assert "last_event" in payload
    assert "why_candidate_allowed" in payload

    assert payload["violated_flow"]["label"] == "PII"
    assert payload["last_event"]["event_taint"] == ["PII"]
    assert payload["last_event"]["writes"] == ["slot:external.slack"]
    assert isinstance(payload["why_candidate_allowed"], str)


def test_counterexample_llm_json_for_initial_bad_state(minimal_leak):
    model, policy, _ = minimal_leak

    external = Location.slot("external", "slack")
    bad_initial_state = make_state({external: {"PII"}})

    cex = shortest_counterexample(
        model=model,
        policy=policy,
        constraints=(),
        initial_state=bad_initial_state,
    )

    assert cex is not None

    payload = counterexample_to_llm_json(cex)

    assert payload["error"] == "initial_state_unsafe"
    assert payload["violations"]
    assert payload["violations"][0]["label"] == "PII"
