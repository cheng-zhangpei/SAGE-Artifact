"""Metrics used by the guard-authoring experiments."""
from __future__ import annotations
from typing import Iterable, Set, Tuple
from sage.v2.model import ToolModel, ForbiddenFlowPolicy, TaintState
from sage.v2.guards import Constraint, deny_constraints
from sage.v2.properties import (
    compute_event_domain,
    reachable_states,
    is_safe,
    Event
)


def compute_unconstrained_domains(
        model: ToolModel,
        policy: ForbiddenFlowPolicy,
        initial_state: TaintState,
        max_states: int = 10000
) -> Tuple[Set[Event], Set[Event]]:
    """
    计算未约束系统下的安全事件域 E 和危险事件域 D。
    这是计算 DER 和 BBR 的基准 (Ground Truth 基础)。
    """
    E, D = compute_event_domain(
        model=model,
        policy=policy,
        initial_state=initial_state,
        max_states=max_states
    )
    return E, D


def unsafe_reachable_states(
        model: ToolModel,
        policy: ForbiddenFlowPolicy,
        initial_state: TaintState,
        constraints: Iterable[Constraint],
        max_states: int = 10000
) -> int:
    """
    计算受控系统中可达的坏状态数量 (UnsafeReach)。
    目标：经过验证的策略必须为 0。
    """
    reachable = reachable_states(
        model=model,
        initial_state=initial_state,
        constraints=constraints,
        max_states=max_states
    )

    bad_count = 0
    for state in reachable:
        if not is_safe(state, policy):
            bad_count += 1

    return bad_count


def evaluate_constraints(
        constraints: Iterable[Constraint],
        E: Set[Event],
        D: Set[Event]
) -> dict:
    """
    计算 DER (危险事件召回率), Residual (残余危险), BBR (良性阻断率)。
    """
    constraints = tuple(constraints)

    blocked_dangerous = 0
    residual_dangerous = 0
    blocked_benign = 0

    # 遍历所有危险事件
    for event in D:
        state, action = event
        if deny_constraints(constraints, state, action):
            blocked_dangerous += 1
        else:
            residual_dangerous += 1

    # 遍历所有安全事件 (E \ D)
    benign_events = E - D
    for event in benign_events:
        state, action = event
        if deny_constraints(constraints, state, action):
            blocked_benign += 1

    der = blocked_dangerous / len(D) if len(D) > 0 else 1.0
    bbr = blocked_benign / len(benign_events) if len(benign_events) > 0 else 0.0

    return {
        "DER": der,
        "Residual": residual_dangerous,
        "BBR": bbr,
        "Total_D": len(D),
        "Total_Benign": len(benign_events)
    }
