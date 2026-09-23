"""Reference monitors deployed at the support-desk tool-call boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sage.v2.guards import Constraint, deny_constraints
from sage.v2.model import (
    ConcreteAction,
    ForbiddenFlowPolicy,
    Location,
    TaintState,
    ToolModel,
    make_policy,
)
from sage.v2.semantics import deny_star, forbidden_targets_of_action
from sage.v2.synthesis import direct_sage


def supportdesk_policy() -> ForbiddenFlowPolicy:
    return make_policy(
        {
            Location.slot("outbound", "external"): ("PII", "SECRET"),
            Location.slot("deployment", "production"): ("UNTRUSTED",),
        }
    )


@dataclass(frozen=True)
class MonitorDecision:
    denied: bool
    reason: str


class ContextOnlyMonitor:
    """A plausible baseline that sees only the invoking agent's context."""

    name = "context_only"

    def __init__(self, policy: ForbiddenFlowPolicy):
        self.policy = policy

    def decide(self, state: TaintState, action: ConcreteAction) -> MonitorDecision:
        context_labels = state.get(Location.ctx(action.agent))
        forbidden = forbidden_targets_of_action(self.policy, action)
        collision = context_labels & forbidden
        return MonitorDecision(
            denied=bool(collision),
            reason=(
                f"context labels collide with target policy: {sorted(collision)}"
                if collision
                else "invoking context is clean for the target"
            ),
        )


class SAGEReferenceMonitor:
    """A deployed DirectSAGE guard set over the finite integration workload."""

    name = "sage"

    def __init__(
        self,
        actions: Iterable[ConcreteAction],
        policy: ForbiddenFlowPolicy,
    ):
        action_tuple = tuple(actions)
        locations = set(policy.locations())
        labels = set()
        for action in action_tuple:
            locations.update(action.reads)
            locations.update(action.writes)
            labels.update(action.gen)
        for location in policy.locations():
            labels.update(policy.forbidden(location))
        self.model = ToolModel(
            agents=frozenset(action.agent for action in action_tuple),
            tools=frozenset(action.tool for action in action_tuple),
            locations=frozenset(locations),
            labels=frozenset(labels),
            actions=action_tuple,
        )
        self.policy = policy
        self.guards: tuple[Constraint, ...] = direct_sage(self.model, policy)

    def decide(self, state: TaintState, action: ConcreteAction) -> MonitorDecision:
        denied = deny_constraints(self.guards, state, action)
        ideal = deny_star(state, action, self.policy)
        if denied != ideal:
            raise AssertionError("deployed DirectSAGE decision diverges from deny_star")
        return MonitorDecision(
            denied=denied,
            reason=(
                "event taint collides with the target policy"
                if denied
                else "event taint is disjoint from the target policy"
            ),
        )
