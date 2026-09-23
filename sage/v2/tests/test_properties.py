"""
@function      :
@time          :2026/8/3 15:39
"""
# sage/v2/tests/test_properties.py

from __future__ import annotations

from sage.v2.model import (
    Location,
    ToolModel,
    make_action,
    make_policy,
    make_state,
)
from sage.v2.properties import (
    compute_event_domain,
    ideal_controller_allows,
    make_observation_hidden,
    observation_ctx,
    observation_event,
    observation_full,
    zero_overconstraint_condition,
)


def _build_observation_ablation_model():
    """
    构造观测消融场景：

    - load: 生成 PII 并写入 file；
    - send: 读取 file 并写 external。

    初始状态干净。

    于是：
    - 在初始状态，send 是安全事件；
    - 在 load 后，file 带 PII，send 成为危险事件；
    - 两个 send 的 agent/tool/params/ctx 都相同；
    - 因此 O_ctx 会发生观测碰撞；
    - O_event 观察 η，因此不会碰撞；
    - 如果人为隐藏 file 标签，O_hidden 也会碰撞。
    """

    agent = "a"

    ctx = Location.ctx(agent)
    file_loc = Location.slot("file", "f1")
    external = Location.slot("external", "slack")

    load = make_action(
        agent=agent,
        tool="load",
        params={"file": "f1"},
        reads=[ctx],
        writes=[file_loc],
        gen=["PII"],
    )

    send = make_action(
        agent=agent,
        tool="send",
        params={"file": "f1", "channel": "external"},
        reads=[ctx, file_loc],
        writes=[external],
        gen=[],
    )

    model = ToolModel(
        agents=frozenset({agent}),
        tools=frozenset({"load", "send"}),
        locations=frozenset({ctx, file_loc, external}),
        labels=frozenset({"PII"}),
        actions=(load, send),
    )

    policy = make_policy({external: {"PII"}})
    initial_state = make_state({})

    return model, policy, initial_state, file_loc


def test_event_domain_contains_safe_and_dangerous_send_events():
    model, policy, initial_state, _ = _build_observation_ablation_model()

    E, D = compute_event_domain(
        model=model,
        policy=policy,
        initial_state=initial_state,
        max_states=1000,
    )

    assert E, "event domain E should not be empty"
    assert D, "dangerous event set D should not be empty"

    dangerous_tools = {action.tool for _, action in D}
    assert dangerous_tools == {"send"}


def test_ctx_only_observation_can_collide():
    model, policy, initial_state, _ = _build_observation_ablation_model()

    E, D = compute_event_domain(
        model=model,
        policy=policy,
        initial_state=initial_state,
        max_states=1000,
    )

    # O_ctx 只看 agent/tool/params/ctx(agent)，不观察资源读取污点。
    # 安全 send 与危险 send 的 ctx 相同，因此应出现碰撞。
    assert not zero_overconstraint_condition(observation_ctx, E, D)


def test_event_observation_avoids_collision():
    model, policy, initial_state, _ = _build_observation_ablation_model()

    E, D = compute_event_domain(
        model=model,
        policy=policy,
        initial_state=initial_state,
        max_states=1000,
    )

    # O_event 观察 η_u(x)，因此安全 send 与危险 send 可区分。
    assert zero_overconstraint_condition(observation_event, E, D)


def test_hidden_observation_can_collide():
    model, policy, initial_state, file_loc = _build_observation_ablation_model()

    E, D = compute_event_domain(
        model=model,
        policy=policy,
        initial_state=initial_state,
        max_states=1000,
    )

    hidden_file_observation = make_observation_hidden(file_loc)

    # 隐藏关键资源 file 后，危险 send 的 η 中的 PII 被隐藏，
    # 因此与初始状态下的安全 send 不可区分。
    assert not zero_overconstraint_condition(hidden_file_observation, E, D)


def test_full_observation_has_no_collision():
    model, policy, initial_state, _ = _build_observation_ablation_model()

    E, D = compute_event_domain(
        model=model,
        policy=policy,
        initial_state=initial_state,
        max_states=1000,
    )

    assert zero_overconstraint_condition(observation_full, E, D)


def test_ideal_controller_allows_exactly_non_dangerous_events():
    model, policy, initial_state, _ = _build_observation_ablation_model()

    E, D = compute_event_domain(
        model=model,
        policy=policy,
        initial_state=initial_state,
        max_states=1000,
    )

    D_set = set(D)

    for event in E:
        state, action = event
        allowed = ideal_controller_allows(state, action, policy)

        if event in D_set:
            assert not allowed
        else:
            assert allowed
