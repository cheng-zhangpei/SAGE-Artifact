"""
@function      :
@time          :2026/8/3 15:23
"""
# sage/guards.py

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping, Tuple

from .model import (
    AgentId,
    ConcreteAction,
    LabelSet,
    ParamsItems,
    TaintState,
    ToolId,
)
from .semantics import event_taint


# =============================================================================
# 参数过滤器
# =============================================================================


@dataclass(frozen=True)
class ParamFilter:
    """
    参数过滤器。

    exact_patterns:
        精确参数类。要求动作参数与 pattern 完全一致。
        DirectSAGE 初始版本只允许使用这个。

    wildcard_patterns:
        通配参数类。pattern 中给出的键值必须出现，未给出的键视为通配。
        后续如果引入，必须额外证明不会破坏 Q_B 等价性。

    match_all:
        匹配所有参数。只在显式声明时使用。
    """

    exact_patterns: Tuple[ParamsItems, ...] = ()
    wildcard_patterns: Tuple[ParamsItems, ...] = ()
    match_all: bool = False

    def match(self, params: Mapping[str, Any]) -> bool:
        if self.match_all:
            return True

        normalized_params = tuple(sorted(params.items(), key=lambda kv: str(kv[0])))

        for pattern in self.exact_patterns:
            normalized_pattern = tuple(sorted(pattern, key=lambda kv: str(kv[0])))
            if normalized_pattern == normalized_params:
                return True

        for pattern in self.wildcard_patterns:
            if all(params.get(k) == v for k, v in pattern):
                return True

        return False


# =============================================================================
# Definition 10: 可部署约束 c = (a_c, t_c, pf_c, C_c)
# =============================================================================

@dataclass(frozen=True)
class Constraint:
    """
    可部署约束。

    Trigger(c,x,u) ⟺
        u=(a,t,p)
        ∧ a=a_c
        ∧ t=t_c
        ∧ Match(p,pf_c)
        ∧ η_u(x) ∩ C_c ≠ ∅
    """

    agent: AgentId
    tool: ToolId
    param_filter: ParamFilter
    forbidden_labels: LabelSet
    name: str = ""

    def trigger(self, state: TaintState, action: ConcreteAction) -> bool:
        if action.agent != self.agent:
            return False

        if action.tool != self.tool:
            return False

        if not self.param_filter.match(action.params):
            return False

        eta = event_taint(state, action)
        return bool(eta & self.forbidden_labels)

    def canonical(self) -> str:
        labels = ",".join(sorted(self.forbidden_labels))
        return f"Constraint({self.name}: {self.agent}/{self.tool} deny {{{labels}}})"

    def __str__(self) -> str:
        return self.canonical()


# =============================================================================
# 约束集 Deny
# =============================================================================

def deny_constraints(
    constraints: Iterable[Constraint],
    state: TaintState,
    action: ConcreteAction,
) -> bool:
    """
    Deny_C(x,u) ⟺ ∃c∈C: Trigger(c,x,u)
    """
    for c in constraints:
        if c.trigger(state, action):
            return True
    return False


def allow_constraints(
    constraints: Iterable[Constraint],
    state: TaintState,
    action: ConcreteAction,
) -> bool:
    """
    K_C(x,u) = allow ⟺ ¬Deny_C(x,u)
    """
    return not deny_constraints(constraints, state, action)


# =============================================================================
# 语义归一化
# =============================================================================

def semantic_normalize(constraints: Iterable[Constraint]) -> Tuple[Constraint, ...]:
    """
    基础语义归一化：

    - 删除 forbidden_labels 为空的规则；
    - 合并相同 agent/tool/param_filter 的规则；
    - 不改变 Deny_C 的事件集合。

    注意：
    当前版本没有做逻辑蕴含删除。
    后续如果做冗余规则删除，必须证明不改变 Deny_C。
    """
    merged: dict[tuple[AgentId, ToolId, ParamFilter], Constraint] = {}
    order: list[tuple[AgentId, ToolId, ParamFilter]] = []

    for c in constraints:
        if not c.forbidden_labels:
            continue

        key = (c.agent, c.tool, c.param_filter)

        if key not in merged:
            merged[key] = c
            order.append(key)
        else:
            old = merged[key]
            new_forbidden = frozenset(old.forbidden_labels | c.forbidden_labels)
            merged[key] = replace(old, forbidden_labels=new_forbidden)

    return tuple(merged[key] for key in order)
