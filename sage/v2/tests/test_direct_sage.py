"""
@function      :
@time          :2026/8/3 15:39
"""
# sage/v2/tests/test_direct_sage.py

from __future__ import annotations

from sage.v2.counterexample import shortest_counterexample, trace_safe
from sage.v2.guards import deny_constraints
from sage.v2.model import (
    Location,
    ToolModel,
    make_action,
    make_policy,
    make_state,
)
from sage.v2.synthesis import direct_sage
from sage.v2.tests.helpers import assert_deny_star_equivalence


def test_direct_sage_blocks_same_invocation_read_leak(minimal_leak):
    model, policy, initial_state = minimal_leak

    # 无约束时应存在一步反例
    cex = shortest_counterexample(
        model=model,
        policy=policy,
        constraints=(),
        initial_state=initial_state,
    )
    assert cex is not None

    guards = direct_sage(model, policy)
    assert len(guards) == 1

    # DirectSAGE 后应轨迹安全
    assert trace_safe(
        model=model,
        policy=policy,
        constraints=guards,
        initial_state=initial_state,
    )

    # DirectSAGE 应与 Deny* 完全等价
    assert_deny_star_equivalence(model, policy, guards)


def test_direct_sage_blocks_generated_labels():
    agent = "a"

    ctx = Location.ctx(agent)
    external = Location.slot("external", "slack")

    action = make_action(
        agent=agent,
        tool="publish",
        params={"channel": "external"},
        reads=[ctx],
        writes=[external],
        gen=["PII"],
    )

    model = ToolModel(
        agents=frozenset({agent}),
        tools=frozenset({"publish"}),
        locations=frozenset({ctx, external}),
        labels=frozenset({"PII"}),
        actions=(action,),
    )

    policy = make_policy({external: {"PII"}})
    initial_state = make_state({})

    cex = shortest_counterexample(
        model=model,
        policy=policy,
        constraints=(),
        initial_state=initial_state,
    )
    assert cex is not None

    guards = direct_sage(model, policy)
    assert len(guards) == 1

    assert trace_safe(
        model=model,
        policy=policy,
        constraints=guards,
        initial_state=initial_state,
    )

    assert_deny_star_equivalence(model, policy, guards)


def test_direct_sage_does_not_overblock_safe_parameterized_target():
    """
    同一个工具根据参数写入不同目标：

    - channel=external 写外部，policy 禁止 PII；
    - channel=internal 写内部，policy 不禁止 PII。

    DirectSAGE 只能阻断 external 参数类，不能阻断 internal。
    """

    agent = "support"

    ctx = Location.ctx(agent)
    file_loc = Location.slot("file", "T1")
    external = Location.slot("external", "slack")
    internal = Location.slot("internal", "log")

    send_external = make_action(
        agent=agent,
        tool="send",
        params={"file": "T1", "channel": "external"},
        reads=[ctx, file_loc],
        writes=[external],
        gen=[],
    )

    send_internal = make_action(
        agent=agent,
        tool="send",
        params={"file": "T1", "channel": "internal"},
        reads=[ctx, file_loc],
        writes=[internal],
        gen=[],
    )

    model = ToolModel(
        agents=frozenset({agent}),
        tools=frozenset({"send"}),
        locations=frozenset({ctx, file_loc, external, internal}),
        labels=frozenset({"PII"}),
        actions=(send_external, send_internal),
    )

    policy = make_policy({external: {"PII"}})
    initial_state = make_state({file_loc: {"PII"}})

    guards = direct_sage(model, policy)

    state = make_state({file_loc: {"PII"}})

    assert deny_constraints(guards, state, send_external)
    assert not deny_constraints(guards, state, send_internal)

    assert trace_safe(
        model=model,
        policy=policy,
        constraints=guards,
        initial_state=initial_state,
    )

    assert_deny_star_equivalence(model, policy, guards)


def test_direct_sage_handles_multiple_write_ports():
    agent = "a"

    ctx = Location.ctx(agent)
    file_loc = Location.slot("file", "f1")
    external = Location.slot("external", "slack")
    audit = Location.slot("audit", "log")

    action = make_action(
        agent=agent,
        tool="publish",
        params={},
        reads=[ctx, file_loc],
        writes=[external, audit],
        gen=[],
    )

    model = ToolModel(
        agents=frozenset({agent}),
        tools=frozenset({"publish"}),
        locations=frozenset({ctx, file_loc, external, audit}),
        labels=frozenset({"PII"}),
        actions=(action,),
    )

    policy = make_policy({external: {"PII"}})
    initial_state = make_state({file_loc: {"PII"}})

    guards = direct_sage(model, policy)

    assert len(guards) == 1

    assert trace_safe(
        model=model,
        policy=policy,
        constraints=guards,
        initial_state=initial_state,
    )

    assert_deny_star_equivalence(model, policy, guards)


def test_direct_sage_supports_integrity_untrusted_labels():
    agent = "deployer"

    ctx = Location.ctx(agent)
    web_content = Location.slot("web", "page1")
    prod_config = Location.slot("prod", "config")

    deploy = make_action(
        agent=agent,
        tool="deploy_config",
        params={"source": "web_page1"},
        reads=[ctx, web_content],
        writes=[prod_config],
        gen=[],
    )

    model = ToolModel(
        agents=frozenset({agent}),
        tools=frozenset({"deploy_config"}),
        locations=frozenset({ctx, web_content, prod_config}),
        labels=frozenset({"UNTRUSTED_WEB"}),
        actions=(deploy,),
    )

    policy = make_policy({prod_config: {"UNTRUSTED_WEB"}})
    initial_state = make_state({web_content: {"UNTRUSTED_WEB"}})

    cex = shortest_counterexample(
        model=model,
        policy=policy,
        constraints=(),
        initial_state=initial_state,
    )
    assert cex is not None

    guards = direct_sage(model, policy)

    assert trace_safe(
        model=model,
        policy=policy,
        constraints=guards,
        initial_state=initial_state,
    )

    assert_deny_star_equivalence(model, policy, guards)


def test_direct_sage_generates_no_rule_when_q_is_empty():
    agent = "a"

    ctx = Location.ctx(agent)
    internal = Location.slot("internal", "log")

    action = make_action(
        agent=agent,
        tool="log_internal",
        params={},
        reads=[ctx],
        writes=[internal],
        gen=["PII"],
    )

    model = ToolModel(
        agents=frozenset({agent}),
        tools=frozenset({"log_internal"}),
        locations=frozenset({ctx, internal}),
        labels=frozenset({"PII"}),
        actions=(action,),
    )

    # internal 没有禁止标签
    policy = make_policy({})

    guards = direct_sage(model, policy)

    assert guards == ()


def test_direct_sage_exact_filters_do_not_cross_no_param_and_param_actions():
    """
    这个测试专门约束 ParamFilter 的正确性：

    - 无参数动作写 ext1，禁止标签 A；
    - 有参数动作写 ext2，禁止标签 B；
    - 二者不能互相匹配。

    如果空 exact pattern 错误地匹配所有参数，本测试会失败。
    """

    agent = "a"

    ctx = Location.ctx(agent)
    source_a = Location.slot("source", "A")
    source_b = Location.slot("source", "B")
    ext1 = Location.slot("ext", "1")
    ext2 = Location.slot("ext", "2")

    no_param_action = make_action(
        agent=agent,
        tool="t",
        params={},
        reads=[ctx, source_a],
        writes=[ext1],
        gen=[],
    )

    param_action = make_action(
        agent=agent,
        tool="t",
        params={"x": 1},
        reads=[ctx, source_a],
        writes=[ext2],
        gen=[],
    )

    model = ToolModel(
        agents=frozenset({agent}),
        tools=frozenset({"t"}),
        locations=frozenset({ctx, source_a, source_b, ext1, ext2}),
        labels=frozenset({"A", "B"}),
        actions=(no_param_action, param_action),
    )

    policy = make_policy(
        {
            ext1: {"A"},
            ext2: {"B"},
        }
    )

    guards = direct_sage(model, policy)

    state_with_a = make_state({source_a: {"A"}})

    # 无参数动作读取 A，写 ext1，应被拒绝
    assert deny_constraints(guards, state_with_a, no_param_action)

    # 有参数动作虽然也读取 A，但写 ext2，Q_B={B}；
    # η 中没有 B，因此 Deny* 为 false，不能被 A 规则误拒。
    assert not deny_constraints(guards, state_with_a, param_action)

    assert_deny_star_equivalence(model, policy, guards)
