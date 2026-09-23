"""Counterexample search and structured feedback for the SAGE v2 model."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

from .guards import Constraint, deny_constraints
from .model import (
    ConcreteAction,
    ForbiddenFlowPolicy,
    Label,
    Location,
    TaintState,
    ToolModel,
)
from .semantics import event_taint, execute, is_safe


class SearchLimitExceeded(RuntimeError):
    """The finite-state search ended because its state budget was exhausted."""


@dataclass(frozen=True)
class LastEvent:
    state: TaintState
    action: ConcreteAction
    event_taint: frozenset


@dataclass(frozen=True)
class Step:
    """One transition in a counterexample trace."""

    index: int
    state: TaintState
    action: ConcreteAction
    event_taint: frozenset[Label]
    post_state: TaintState


@dataclass(frozen=True)
class Counterexample:
    """A violating trace; ``last_event`` is absent for an unsafe initial state."""

    trace: Tuple[Step, ...]
    final_state: TaintState
    violations: Tuple[Tuple[Label, Location], ...]
    last_event: Optional[LastEvent]


def find_violations(
    state: TaintState,
    policy: ForbiddenFlowPolicy,
) -> Tuple[Tuple[Label, Location], ...]:
    """Return every ``(label, location)`` forbidden by the policy in ``state``."""
    violations: List[Tuple[Label, Location]] = []
    locations = set(state.locations()) | set(policy.locations())

    for loc in locations:
        bad_labels = state.get(loc) & policy.forbidden(loc)
        for label in sorted(bad_labels):
            violations.append((label, loc))

    return tuple(violations)


def shortest_counterexample(
    model: ToolModel,
    policy: ForbiddenFlowPolicy,
    constraints: Iterable[Constraint],
    initial_state: TaintState,
    max_states: Optional[int] = 20000,
) -> Optional[Counterexample]:
    """Return a shortest violation, or ``None`` after exhaustive safe search.

    ``None`` is reserved for a completed search that found no counterexample.
    If the state budget is reached before exhaustion, the result is unknown and
    ``SearchLimitExceeded`` is raised.
    """
    if max_states is not None and max_states < 1:
        raise ValueError("max_states must be positive or None")

    if not is_safe(initial_state, policy):
        return Counterexample(
            trace=(),
            final_state=initial_state,
            violations=find_violations(initial_state, policy),
            last_event=None,
        )

    constraints = tuple(constraints)
    visited = {initial_state}
    queue = deque([(initial_state, [])])

    while queue:
        state, trace = queue.popleft()

        for action in model.actions:
            if not model.enabled(state, action):
                continue
            if deny_constraints(constraints, state, action):
                continue

            post = execute(state, action)
            transitions = trace + [(state, action)]

            if not is_safe(post, policy):
                steps = tuple(
                    Step(
                        index=index,
                        state=pre_state,
                        action=step_action,
                        event_taint=event_taint(pre_state, step_action),
                        post_state=execute(pre_state, step_action),
                    )
                    for index, (pre_state, step_action) in enumerate(transitions)
                )
                return Counterexample(
                    trace=steps,
                    final_state=post,
                    violations=find_violations(post, policy),
                    last_event=LastEvent(
                        state=state,
                        action=action,
                        event_taint=event_taint(state, action),
                    ),
                )

            if post not in visited:
                visited.add(post)
                if max_states is not None and len(visited) > max_states:
                    raise SearchLimitExceeded(
                        f"visited states exceed max_states={max_states}"
                    )
                queue.append((post, transitions))

    return None


def counterexample_to_llm_json(cex: Counterexample) -> dict:
    """Convert a counterexample to a stable, auditable feedback schema."""
    violations = [
        {"label": str(label), "location": str(loc)}
        for label, loc in cex.violations
    ]

    if cex.last_event is None:
        return {
            "error": "initial_state_unsafe",
            "violated_flow": violations[0] if violations else None,
            "violations": violations,
            "trace": [],
            "last_event": None,
            "why_candidate_allowed": (
                "The initial state already violates the forbidden-flow policy; "
                "no runtime guard can repair this execution prefix."
            ),
        }

    trace = [
        {
            "index": step.index,
            "action": {
                "agent": step.action.agent,
                "tool": step.action.tool,
                "params": dict(step.action.params_items),
            },
            "event_taint": sorted(step.event_taint),
        }
        for step in cex.trace
    ]
    last_event = {
        "agent": cex.last_event.action.agent,
        "tool": cex.last_event.action.tool,
        "params": dict(cex.last_event.action.params_items),
        "reads": sorted(str(loc) for loc in cex.last_event.action.reads),
        "writes": sorted(str(loc) for loc in cex.last_event.action.writes),
        "gen": sorted(cex.last_event.action.gen),
        "event_taint": sorted(cex.last_event.event_taint),
    }

    return {
        "violated_flow": violations[0] if violations else None,
        "violations": violations,
        "trace": trace,
        "last_event": last_event,
        # Backward-compatible alias for previous experiment consumers.
        "violated_event": last_event,
        "trace_length": len(cex.trace),
        "why_candidate_allowed": (
            "The candidate guards allowed the last event, whose event taint "
            "reached a write target that forbids one or more of those labels."
        ),
    }


def trace_safe(
    model: ToolModel,
    policy: ForbiddenFlowPolicy,
    constraints: Iterable[Constraint],
    initial_state: TaintState,
    max_states: Optional[int] = None,
    max_depth: Optional[int] = None,
) -> bool:
    """Check trace safety by exhaustive search within the supplied state limit.

    ``SearchLimitExceeded`` is propagated so callers cannot confuse an
    incomplete search with a safety proof. ``max_depth`` is reserved for a
    future bounded-search API and is currently unsupported.
    """
    if max_depth is not None:
        raise NotImplementedError("max_depth is not implemented")

    cex = shortest_counterexample(
        model=model,
        policy=policy,
        constraints=constraints,
        initial_state=initial_state,
        max_states=max_states,
    )
    return cex is None
