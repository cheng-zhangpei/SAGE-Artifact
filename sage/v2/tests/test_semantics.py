"""
@function      :
@time          :2026/8/3 15:39
"""
# sage/v2/tests/test_semantics.py

from __future__ import annotations

from sage.v2.model import (
    Location,
    ToolModel,
    make_action,
    make_policy,
    make_state,
)
from sage.v2.properties import (
    bad_upward_closed_instance,
    lemma_1_monotone_instance,
    state_leq,
)
from sage.v2.semantics import (
    deny_star,
    event_taint,
    execute,
    forbidden_targets_of_action,
    is_bad,
    is_safe,
)
from sage.v2.tests.helpers import all_safe_enabled_pairs


def test_event_taint_is_union_of_gen_and_reads():
    agent = "a"

    ctx = Location.ctx(agent)
    file_loc = Location.slot("file", "f1")
    external = Location.slot("external", "slack")

    action = make_action(
        agent=agent,
        tool="t",
        params={"id": 1},
        reads=[ctx, file_loc],
        writes=[external],
        gen=["GEN"],
    )

    state = make_state(
        {
            ctx: {"CTX_LABEL"},
            file_loc: {"FILE_LABEL"},
        }
    )

    eta = event_taint(state, action)

    assert eta == frozenset({"GEN", "CTX_LABEL", "FILE_LABEL"})


def test_execute_updates_only_write_locations():
    agent = "a"

    ctx = Location.ctx(agent)
    file_loc = Location.slot("file", "f1")
    external = Location.slot("external", "slack")

    action = make_action(
        agent=agent,
        tool="send",
        params={},
        reads=[ctx, file_loc],
        writes=[external],
        gen=[],
    )

    state = make_state(
        {
            ctx: {"CTX_LABEL"},
            file_loc: {"PII"},
        }
    )

    post = execute(state, action)

    # 写目标获得事件污点
    assert post.get(external) == frozenset({"CTX_LABEL", "PII"})

    # 未写位置保持不变
    assert post.get(file_loc) == frozenset({"PII"})
    assert post.get(ctx) == frozenset({"CTX_LABEL"})


def test_safe_and_bad_states():
    external = Location.slot("external", "slack")
    file_loc = Location.slot("file", "f1")

    policy = make_policy({external: {"PII"}})

    safe_state = make_state({file_loc: {"PII"}})
    bad_state = make_state({external: {"PII"}})

    assert is_safe(safe_state, policy)
    assert not is_bad(safe_state, policy)

    assert not is_safe(bad_state, policy)
    assert is_bad(bad_state, policy)


def test_state_order():
    file_loc = Location.slot("file", "f1")

    x = make_state({file_loc: {"PII"}})
    y = make_state({file_loc: {"PII", "CRED"}})

    assert state_leq(x, y)
    assert not state_leq(y, x)


def test_lemma_1_execution_monotonicity():
    agent = "a"

    ctx = Location.ctx(agent)
    file_loc = Location.slot("file", "f1")
    external = Location.slot("external", "slack")

    action = make_action(
        agent=agent,
        tool="send",
        params={},
        reads=[ctx, file_loc],
        writes=[external],
        gen=[],
    )

    x = make_state({file_loc: {"PII"}})
    y = make_state({file_loc: {"PII", "CRED"}})

    assert state_leq(x, y)
    assert lemma_1_monotone_instance(x, y, action)


def test_lemma_2_bad_states_are_upward_closed():
    external = Location.slot("external", "slack")
    file_loc = Location.slot("file", "f1")

    policy = make_policy({external: {"PII"}})

    bad_x = make_state({external: {"PII"}})
    larger_y = make_state(
        {
            external: {"PII"},
            file_loc: {"CRED"},
        }
    )

    assert state_leq(bad_x, larger_y)
    assert bad_upward_closed_instance(policy, bad_x, larger_y)


def test_lemma_3_deny_star_equals_one_step_unsafe_on_small_model():
    """
    Lemma 3:

    对安全前态 x：
        ¬Safe_B(F_u(x)) ⟺ η_u(x) ∩ Q_B(u) ≠ ∅
    """

    agent = "a"

    ctx = Location.ctx(agent)
    file_loc = Location.slot("file", "f1")
    external = Location.slot("external", "slack")

    send = make_action(
        agent=agent,
        tool="send",
        params={"file": "f1"},
        reads=[ctx, file_loc],
        writes=[external],
        gen=[],
    )

    inject = make_action(
        agent=agent,
        tool="inject",
        params={},
        reads=[ctx],
        writes=[external],
        gen=["PII"],
    )

    model = ToolModel(
        agents=frozenset({agent}),
        tools=frozenset({"send", "inject"}),
        locations=frozenset({ctx, file_loc, external}),
        labels=frozenset({"PII", "CRED"}),
        actions=(send, inject),
    )

    policy = make_policy(
        {
            external: {"PII", "CRED"},
        }
    )

    for state, action in all_safe_enabled_pairs(model, policy):
        expected = deny_star(state, action, policy)
        actual_post_unsafe = not is_safe(execute(state, action), policy)

        assert expected == actual_post_unsafe, (
            f"Lemma 3 failed: state={state}, action={action}, "
            f"expected={expected}, actual_post_unsafe={actual_post_unsafe}"
        )
