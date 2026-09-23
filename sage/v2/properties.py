"""
@function      :
@time          :2026/8/3 15:23
"""
# sage/properties.py

from __future__ import annotations

from collections import deque
from typing import Callable, Iterable, List, Optional, Set, Tuple

from .counterexample import SearchLimitExceeded
from .guards import Constraint, deny_constraints
from .model import (
    ConcreteAction,
    ForbiddenFlowPolicy,
    Location,
    TaintState,
    ToolModel,
)
from .semantics import (
    deny_star,
    event_taint,
    execute,
    is_safe,
)


# =============================================================================
# 事件与观测函数类型
# =============================================================================

Event = Tuple[TaintState, ConcreteAction]
ObservationFn = Callable[[TaintState, ConcreteAction], object]


# =============================================================================
# Definition 3: 状态偏序 x ≤ y
# =============================================================================

def state_leq(x: TaintState, y: TaintState) -> bool:
    """
    x ≤ y ⟺ ∀v: x(v) ⊆ y(v)

    当前实现只遍历 x 中非空位置。
    若 x 为空，则 x ≤ y 恒成立。
    """
    for loc in x.locations():
        if not (x.get(loc) <= y.get(loc)):
            return False
    return True


# =============================================================================
# Lemma 1: 执行单调性（实例检查）
# =============================================================================

def lemma_1_monotone_instance(
    x: TaintState,
    y: TaintState,
    action: ConcreteAction,
) -> bool:
    """
    若 x ≤ y，则：
    - η_u(x) ⊆ η_u(y)
    - F_u(x) ≤ F_u(y)

    返回 True 表示该实例满足单调性。
    """

    if not state_leq(x, y):
        return True

    eta_x = event_taint(x, action)
    eta_y = event_taint(y, action)

    if not (eta_x <= eta_y):
        return False

    post_x = execute(x, action, eta=eta_x)
    post_y = execute(y, action, eta=eta_y)

    return state_leq(post_x, post_y)


# =============================================================================
# Lemma 2: 坏状态向上封闭（实例检查）
# =============================================================================

def bad_upward_closed_instance(
    policy: ForbiddenFlowPolicy,
    x: TaintState,
    y: TaintState,
) -> bool:
    """
    若 Bad_B(x) 且 x ≤ y，则 Bad_B(y)。

    返回 True 表示该实例未违反该引理。
    """

    if is_safe(x, policy):
        return True

    if not state_leq(x, y):
        return True

    return not is_safe(y, policy)


# =============================================================================
# Lemma 3: 安全前态上的危险动作刻画（实例检查）
# =============================================================================

def lemma_3_instance(
    state: TaintState,
    action: ConcreteAction,
    policy: ForbiddenFlowPolicy,
) -> bool:
    """
    若 x 安全，则：
    ¬Safe_B(F_u(x)) ⟺ η_u(x) ∩ Q_B(u) ≠ ∅

    即：
    deny_star(x,u,policy) == (not one_step_safe)
    """

    if not is_safe(state, policy):
        return True

    expected = deny_star(state, action, policy)
    actual_post_unsafe = not is_safe(execute(state, action), policy)

    return expected == actual_post_unsafe


# =============================================================================
# 受控/非受控可达状态搜索
# =============================================================================

def reachable_states(
    model: ToolModel,
    initial_state: TaintState,
    constraints: Optional[Iterable[Constraint]] = None,
    max_states: Optional[int] = None,
) -> Set[TaintState]:
    """
    计算从 initial_state 出发的可达状态集合。

    如果 constraints 为空，则是非受控可达状态。
    如果 constraints 非空，则是受控可达状态。
    """

    if constraints is None:
        constraints = ()

    constraints = tuple(constraints)

    visited = {initial_state}
    queue: deque[TaintState] = deque([initial_state])

    while queue:
        state = queue.popleft()

        for action in model.actions:
            if not model.enabled(state, action):
                continue

            if deny_constraints(constraints, state, action):
                continue

            post = execute(state, action)

            if post not in visited:
                visited.add(post)

                if max_states is not None and len(visited) > max_states:
                    raise SearchLimitExceeded(
                        f"visited states exceed max_states={max_states}"
                    )

                queue.append(post)

    return visited


# =============================================================================
# Definition 13: 事件域 E 与危险事件 D
# =============================================================================

def compute_event_domain(
    model: ToolModel,
    policy: ForbiddenFlowPolicy,
    initial_state: TaintState,
    max_states: Optional[int] = None,
) -> Tuple[Set[Event], Set[Event]]:
    """
    计算：
    - E：安全事件域；
    - D：危险事件集合。

    其中：
    R 是非受控系统从 x0 可达的状态集合；
    E = {(x,u) | x∈R, Safe_B(x), enabled(x,u)};
    D = {(x,u)∈E | ¬Safe_B(F_u(x))}.
    """

    reachable = reachable_states(
        model=model,
        initial_state=initial_state,
        constraints=(),
        max_states=max_states,
    )

    E: Set[Event] = set()
    D: Set[Event] = set()

    for state in reachable:
        if not is_safe(state, policy):
            continue

        for action in model.actions:
            if not model.enabled(state, action):
                continue

            event = (state, action)
            E.add(event)

            post = execute(state, action)
            if not is_safe(post, policy):
                D.add(event)

    return E, D


# =============================================================================
# Definition 14: 观测函数 O
# =============================================================================

def observation_ctx(state: TaintState, action: ConcreteAction) -> object:
    """
    O_ctx(x,u) = (a, t, p, κ(a))

    只观察调用者 Agent 上下文。
    这是旧 guard 容易使用的弱观测。
    """
    ctx = Location.ctx(action.agent)
    ctx_labels = tuple(sorted(state.get(ctx)))

    return (
        action.agent,
        action.tool,
        action.params_items,
        ctx_labels,
    )


def observation_event(state: TaintState, action: ConcreteAction) -> object:
    """
    O_event(x,u) = (a, t, p, η_u(x))

    观察完整事件传播污点。
    这是基础模型推荐的事件级观测。
    """
    eta = event_taint(state, action)

    return (
        action.agent,
        action.tool,
        action.params_items,
        tuple(sorted(eta)),
    )


def observation_full(state: TaintState, action: ConcreteAction) -> object:
    """
    O_full(x,u) = (x,u)

    完整状态观测。
    """
    return (state, action)


def make_observation_hidden(hidden_location: Location) -> ObservationFn:
    """
    构造一个隐藏某个位置标签的观测函数。

    用于构造观测碰撞实验：
    当关键读位置被隐藏时，安全事件和危险事件可能观测相同。
    """

    def observation(state: TaintState, action: ConcreteAction) -> object:
        hidden_taint = state.get(hidden_location)
        eta = event_taint(state, action)

        # 简单隐藏：从事件污点中移除该位置原有标签。
        # 注意：如果同一标签也来自其他读取位置或 Gen，也会被移除。
        # 作为构造性观测消融，这已经足够。
        visible_eta = eta - hidden_taint

        return (
            action.agent,
            action.tool,
            action.params_items,
            tuple(sorted(visible_eta)),
        )

    return observation


# =============================================================================
# Definition 15 / Theorem 3 / Corollary 1: 观测碰撞与零过约束条件
# =============================================================================
def observation_collisions(
    observation_fn: ObservationFn,
    E: Iterable[Event],
    D: Iterable[Event],
) -> Set[object]:
    r"""  # <--- 这里加 r
    计算观测碰撞：

    O(D) ∩ O(E \ D)

    如果交集非空，说明存在安全事件与危险事件具有相同观测。
    任何只依赖该观测的安全控制器都必须同时拒绝二者。
    """
    D_set = set(D)

    dangerous_observations = {
        observation_fn(state, action)
        for state, action in D_set
    }

    safe_observations = {
        observation_fn(state, action)
        for state, action in E
        if (state, action) not in D_set
    }

    return dangerous_observations & safe_observations

def zero_overconstraint_condition(
    observation_fn: ObservationFn,
    E: Iterable[Event],
    D: Iterable[Event],
) -> bool:
    r"""  # <--- 这里加 r
    Corollary 1:

    K_O* 不拒绝任何安全事件，当且仅当：

        O(D) ∩ O(E \ D) = ∅

    返回 True 表示当前观测下不存在不可避免的观测过约束。
    """
    collisions = observation_collisions(observation_fn, E, D)
    return len(collisions) == 0


# =============================================================================
# 理想控制器 K*
# =============================================================================

def ideal_controller_allows(
    state: TaintState,
    action: ConcreteAction,
    policy: ForbiddenFlowPolicy,
) -> bool:
    """
    K*(x,u) = allow ⟺ Safe_B(F_u(x))

    仅对安全前态有意义。
    """
    return is_safe(execute(state, action), policy)


# =============================================================================
# DirectSAGE 与 Deny* 的一致性检查
# =============================================================================

def check_deny_star_equivalence(
    model: ToolModel,
    policy: ForbiddenFlowPolicy,
    constraints: Iterable[Constraint],
    initial_state: Optional[TaintState] = None,
    max_states: Optional[int] = None,
    pairs: Optional[Iterable[Event]] = None,
) -> List[dict]:
    """
    检查候选约束集是否与 Deny* 一致。

    如果提供 pairs，则只检查这些 state-action 对；
    否则从 initial_state 出发枚举非受控可达的安全状态上的 enabled actions。

    返回 mismatch 列表。
    空列表表示在给定范围内没有发现不一致。
    """

    constraints = tuple(constraints)
    mismatches: List[dict] = []

    if pairs is None:
        if initial_state is None:
            raise ValueError("either pairs or initial_state must be provided")

        states = reachable_states(
            model=model,
            initial_state=initial_state,
            constraints=(),
            max_states=max_states,
        )

        generated_pairs: List[Event] = []

        for state in states:
            if not is_safe(state, policy):
                continue

            for action in model.actions:
                if model.enabled(state, action):
                    generated_pairs.append((state, action))

        pairs = generated_pairs

    for state, action in pairs:
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

    return mismatches
