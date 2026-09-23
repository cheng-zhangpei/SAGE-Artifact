"""
@function      :
@time          :2026/8/3 15:38
"""
# sage/v2/tests/helpers.py

from __future__ import annotations

from itertools import combinations, product
from typing import Iterable, List, Tuple

from sage.v2.guards import Constraint, deny_constraints
from sage.v2.model import (
    ConcreteAction,
    ForbiddenFlowPolicy,
    TaintState,
    ToolModel,
    make_state,
)
from sage.v2.semantics import deny_star, is_safe


Event = Tuple[TaintState, ConcreteAction]


def powerset(items: Iterable[str]) -> Iterable[frozenset[str]]:
    """
    返回一个集合的所有子集。
    """
    items = list(items)

    for r in range(len(items) + 1):
        for combo in combinations(items, r):
            yield frozenset(combo)


def enumerate_all_states(model: ToolModel, limit: int = 4096) -> List[TaintState]:
    """
    穷举小模型的所有状态。

    状态空间大小为：

        2 ^ (|L| * |V|)

    因此只用于测试小模型。
    """

    labels = sorted(model.labels)
    locations = sorted(model.locations, key=str)

    label_subsets = list(powerset(labels))
    total = len(label_subsets) ** len(locations)

    if total > limit:
        raise ValueError(f"state space too large for exhaustive test: {total} > {limit}")

    states: List[TaintState] = []

    for assignment in product(label_subsets, repeat=len(locations)):
        mapping = {}

        for loc, label_set in zip(locations, assignment):
            if label_set:
                mapping[loc] = label_set

        states.append(make_state(mapping))

    return states


def all_safe_enabled_pairs(
    model: ToolModel,
    policy: ForbiddenFlowPolicy,
) -> Iterable[Event]:
    """
    枚举所有安全状态上的可执行动作对。

    用于 RQ1 的穷举一致性测试：
    - DirectSAGE guard 是否与 Deny* 一致；
    - Lemma 3 是否成立。
    """

    for state in enumerate_all_states(model):
        if not is_safe(state, policy):
            continue

        for action in model.actions:
            if model.enabled(state, action):
                yield state, action


def assert_deny_star_equivalence(
    model: ToolModel,
    policy: ForbiddenFlowPolicy,
    constraints: Iterable[Constraint],
) -> None:
    """
    检查：

        Deny_C(x,u) == Deny*_B(x,u)

    对所有穷举到的安全状态-动作对成立。

    这是 Theorem 4 的工程化测试。
    """

    constraints = tuple(constraints)
    mismatches = []

    for state, action in all_safe_enabled_pairs(model, policy):
        expected = deny_star(state, action, policy)
        actual = deny_constraints(constraints, state, action)

        if expected != actual:
            mismatches.append(
                {
                    "state": state,
                    "action": action,
                    "expected_deny": expected,
                    "actual_deny": actual,
                }
            )

    assert not mismatches, f"Deny* equivalence mismatches: {mismatches[:5]}"
