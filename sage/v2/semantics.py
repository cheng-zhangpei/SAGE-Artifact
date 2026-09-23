"""
@function      :
@time          :2026/8/3 15:23
"""
# sage/semantics.py

from __future__ import annotations

from typing import Mapping

from .model import (
    ConcreteAction,
    ForbiddenFlowPolicy,
    LabelSet,
    Location,
    TaintState,
    make_state,
)


# =============================================================================
# Definition 5: 事件传播污点 η_u(x)
# =============================================================================

def event_taint(state: TaintState, action: ConcreteAction) -> LabelSet:
    """
    η_u(x) = Gen(u) ∪ ⋃_{v∈Rd(u)} x(v)

    这是运行时 guard 必须检查的对象。
    它包含：
    - 工具本次生成/注入的标签 Gen(u)；
    - 本次调用实际读取的所有位置上的污点。
    """
    result = set(action.gen)
    for loc in action.reads:
        result.update(state.get(loc))
    return frozenset(result)


# =============================================================================
# Definition 8: 动作相关禁止标签 Q_B(u)
# =============================================================================

def forbidden_targets_of_action(
    policy: ForbiddenFlowPolicy,
    action: ConcreteAction,
) -> LabelSet:
    """
    Q_B(u) = ⋃_{v∈Wr(u)} B(v)
    """
    result = set()
    for loc in action.writes:
        result.update(policy.forbidden(loc))
    return frozenset(result)


# =============================================================================
# Definition 6: 基础追加式执行语义 F_u
# =============================================================================

def execute(
    state: TaintState,
    action: ConcreteAction,
    eta: LabelSet | None = None,
) -> TaintState:
    """
    基础 append/union-flow 语义：

    F_u(x)(v) =
        x(v) ∪ η_u(x),  if v ∈ Wr(u)
        x(v),           otherwise

    所有读操作基于同一个前置状态 x；
    所有写操作同时提交。
    """
    if eta is None:
        eta = event_taint(state, action)

    if not action.writes:
        return state

    new_mapping: dict[Location, LabelSet] = dict(state.items())

    for loc in action.writes:
        old_labels = state.get(loc)
        new_mapping[loc] = old_labels | eta

    return make_state(new_mapping)


# =============================================================================
# Definition 7: Safe / Bad
# =============================================================================

def is_safe(state: TaintState, policy: ForbiddenFlowPolicy) -> bool:
    """
    Safe_B(x) ⟺ ∀v∈V: x(v) ∩ B(v) = ∅
    """
    locations = set(state.locations()) | set(policy.locations())

    for loc in locations:
        if state.get(loc) & policy.forbidden(loc):
            return False

    return True


def is_bad(state: TaintState, policy: ForbiddenFlowPolicy) -> bool:
    """
    Bad_B(x) ⟺ ¬Safe_B(x)
    """
    return not is_safe(state, policy)


# =============================================================================
# Definition 9: 精确事件 guard Deny*_B
# =============================================================================

def deny_star(
    state: TaintState,
    action: ConcreteAction,
    policy: ForbiddenFlowPolicy,
) -> bool:
    """
    Deny*_B(x,u) ⟺ η_u(x) ∩ Q_B(u) ≠ ∅

    这是基础模型中的理想拒绝谓词。
    """
    eta = event_taint(state, action)
    q = forbidden_targets_of_action(policy, action)
    return bool(eta & q)


def one_step_safe(
    state: TaintState,
    action: ConcreteAction,
    policy: ForbiddenFlowPolicy,
) -> bool:
    """
    判断在状态 x 执行动作 u 后是否仍安全。
    """
    post = execute(state, action)
    return is_safe(post, policy)
