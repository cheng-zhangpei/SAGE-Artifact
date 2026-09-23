"""
@function      :
@time          :2026/8/3 15:39
"""
# sage/v2/tests/test_guards.py

from __future__ import annotations

from typing import Any, Mapping

from sage.v2.guards import (
    Constraint,
    ParamFilter,
    deny_constraints,
    semantic_normalize,
)
from sage.v2.model import (
    Location,
    make_action,
    make_state,
)


def _params_items(params: Mapping[str, Any]):
    return tuple(sorted(params.items(), key=lambda kv: str(kv[0])))


def test_exact_param_filter_requires_full_parameter_match():
    pf = ParamFilter(
        exact_patterns=(
            _params_items({"channel": "external"}),
        ),
        wildcard_patterns=(),
        match_all=False,
    )

    assert pf.match({"channel": "external"})

    # 精确模式不允许额外参数
    assert not pf.match({"channel": "external", "file": "T1"})

    # 缺少参数也不匹配
    assert not pf.match({})


def test_empty_exact_param_filter_matches_only_empty_params():
    pf = ParamFilter(
        exact_patterns=((),),
        wildcard_patterns=(),
        match_all=False,
    )

    assert pf.match({})
    assert not pf.match({"channel": "external"})


def test_wildcard_param_filter_allows_extra_params():
    pf = ParamFilter(
        exact_patterns=(),
        wildcard_patterns=(
            _params_items({"channel": "external"}),
        ),
        match_all=False,
    )

    assert pf.match({"channel": "external"})
    assert pf.match({"channel": "external", "file": "T1"})
    assert not pf.match({"channel": "internal"})
    assert not pf.match({})


def test_match_all_param_filter():
    pf = ParamFilter(match_all=True)

    assert pf.match({})
    assert pf.match({"any": "value"})


def test_constraint_trigger_uses_event_taint_not_only_agent_context():
    """
    这是新版数学修复的核心测试：

    Agent 上下文干净，但同一次调用读取了带污点的资源。
    Guard 必须因 η_u(x) 触发，而不是只看 ctx(agent)。
    """

    agent = "support"

    ctx = Location.ctx(agent)
    file_loc = Location.slot("file", "T1")
    external = Location.slot("external", "slack")

    action = make_action(
        agent=agent,
        tool="send_file",
        params={"file": "T1", "channel": "external"},
        reads=[ctx, file_loc],
        writes=[external],
        gen=[],
    )

    state = make_state(
        {
            # ctx 干净，不显式写入任何标签
            file_loc: {"PII"},
        }
    )

    constraint = Constraint(
        agent=agent,
        tool="send_file",
        param_filter=ParamFilter(
            exact_patterns=(
                _params_items({"file": "T1", "channel": "external"}),
            ),
            wildcard_patterns=(),
            match_all=False,
        ),
        forbidden_labels=frozenset({"PII"}),
        name="test_constraint",
    )

    assert constraint.trigger(state, action)
    assert deny_constraints([constraint], state, action)


def test_multi_label_constraint_uses_or_semantics():
    agent = "support"

    ctx = Location.ctx(agent)
    file_loc = Location.slot("file", "T1")
    external = Location.slot("external", "slack")

    action = make_action(
        agent=agent,
        tool="send_file",
        params={"file": "T1"},
        reads=[ctx, file_loc],
        writes=[external],
        gen=[],
    )

    constraint = Constraint(
        agent=agent,
        tool="send_file",
        param_filter=ParamFilter(
            exact_patterns=(
                _params_items({"file": "T1"}),
            ),
            wildcard_patterns=(),
            match_all=False,
        ),
        forbidden_labels=frozenset({"PII", "CREDENTIAL"}),
        name="multi_label",
    )

    state_with_pii_only = make_state({file_loc: {"PII"}})
    state_with_cred_only = make_state({file_loc: {"CREDENTIAL"}})
    state_clean = make_state({})

    assert constraint.trigger(state_with_pii_only, action)
    assert constraint.trigger(state_with_cred_only, action)
    assert not constraint.trigger(state_clean, action)


def test_semantic_normalize_merges_same_param_filter_by_union():
    agent = "support"
    tool = "send_file"

    pf = ParamFilter(
        exact_patterns=(
            _params_items({"channel": "external"}),
        ),
        wildcard_patterns=(),
        match_all=False,
    )

    c1 = Constraint(
        agent=agent,
        tool=tool,
        param_filter=pf,
        forbidden_labels=frozenset({"PII"}),
        name="c1",
    )

    c2 = Constraint(
        agent=agent,
        tool=tool,
        param_filter=pf,
        forbidden_labels=frozenset({"CREDENTIAL"}),
        name="c2",
    )

    normalized = semantic_normalize([c1, c2])

    assert len(normalized) == 1
    assert normalized[0].forbidden_labels == frozenset({"PII", "CREDENTIAL"})
