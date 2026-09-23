"""
@function      :
@time          :2026/8/3 15:23
"""
# sage/synthesis.py

from __future__ import annotations

from typing import Dict, Set, Tuple

from .guards import Constraint, ParamFilter, semantic_normalize
from .model import (
    AgentId,
    ForbiddenFlowPolicy,
    LabelSet,
    ParamsItems,
    ToolId,
    ToolModel,
)
from .semantics import forbidden_targets_of_action


def direct_sage(
    model: ToolModel,
    policy: ForbiddenFlowPolicy,
) -> Tuple[Constraint, ...]:
    """
    DirectSAGE(M, B)

    对基础 union-flow 工具语义，从禁止流不变量直接编译参数级 guard。

    核心思想：
    - 对每个具体动作 u，计算 Q_B(u)；
    - 只有当 Q_B(u) 非空时才需要规则；
    - 参数实例只有在 Q_B(u) 相同时才可以合并；
    - 生成约束 C_c = Q_B(u)。

    对应数学稿：
    - Definition 8: Q_B(u)
    - Definition 9: Deny*_B(x,u)
    - Definition 10: Trigger(c,x,u)
    - Theorem 4: DirectSAGE 输出与 Deny*_B 等价
    """

    # key: (agent, tool, Q_B(u))
    # value: 该等价类中的参数实例集合
    groups: Dict[Tuple[AgentId, ToolId, LabelSet], Set[ParamsItems]] = {}

    for action in model.actions:
        q = forbidden_targets_of_action(policy, action)

        # 如果写目标没有禁止标签，则不需要 guard。
        if not q:
            continue

        key = (action.agent, action.tool, q)

        if key not in groups:
            groups[key] = set()

        groups[key].add(action.params_items)

    constraints: list[Constraint] = []

    for (agent, tool, q), patterns in groups.items():
        param_filter = ParamFilter(
            exact_patterns=tuple(sorted(patterns, key=str)),
            wildcard_patterns=(),
            match_all=False,
        )

        constraint = Constraint(
            agent=agent,
            tool=tool,
            param_filter=param_filter,
            forbidden_labels=q,
            name=f"direct:{agent}:{tool}:{','.join(sorted(q))}",
        )

        constraints.append(constraint)

    return semantic_normalize(constraints)
