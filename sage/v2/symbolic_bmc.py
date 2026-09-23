"""Incremental symbolic bounded model checking for the append-only v2 model.

This module is deliberately independent from :mod:`counterexample`: the
existing explicit BFS remains the reference implementation.  The backend is
sound and complete only for the current finite, history-free union-flow model
with declarative/default action enablement.  It searches increasing trace
lengths, so a returned counterexample is shortest in number of strict state
changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Iterable, List, Optional, Sequence, Tuple

import z3

from .counterexample import Counterexample, LastEvent, Step, find_violations
from .guards import Constraint
from .model import (
    ConcreteAction,
    ForbiddenFlowPolicy,
    Label,
    Location,
    TaintState,
    ToolModel,
    make_state,
)
from .semantics import event_taint, execute, is_safe


class SymbolicBMCUnsupported(ValueError):
    """Raised when a model has semantics this small symbolic backend lacks."""


@dataclass(frozen=True)
class SymbolicBMCResult:
    """Result of a complete or bounded symbolic reachability check."""

    status: str  # PASS, FAIL, or UNKNOWN
    counterexample: Optional[Counterexample]
    state_bits: int
    action_count: int
    depth_bound: int
    checked_depth: int
    solver_calls: int
    elapsed_seconds: float
    reason: str = ""


def _ordered_domain(
    model: ToolModel,
    policy: ForbiddenFlowPolicy,
    initial_state: TaintState,
    constraints: Sequence[Constraint],
) -> Tuple[Tuple[Location, ...], Tuple[Label, ...]]:
    locations = set(model.locations) | set(policy.locations()) | set(initial_state.locations())
    labels = set(model.labels)

    for loc in policy.locations():
        labels.update(policy.forbidden(loc))
    for _, state_labels in initial_state.items():
        labels.update(state_labels)
    for action in model.actions:
        locations.update(action.reads)
        locations.update(action.writes)
        labels.update(action.gen)
    for constraint in constraints:
        labels.update(constraint.forbidden_labels)

    return tuple(sorted(locations, key=str)), tuple(sorted(labels))


def _matches(constraint: Constraint, action: ConcreteAction) -> bool:
    return (
        constraint.agent == action.agent
        and constraint.tool == action.tool
        and constraint.param_filter.match(action.params)
    )


def verify_symbolic_bmc(
    model: ToolModel,
    policy: ForbiddenFlowPolicy,
    constraints: Iterable[Constraint],
    initial_state: TaintState,
    *,
    max_depth: Optional[int] = None,
    timeout_ms: Optional[int] = 30_000,
) -> SymbolicBMCResult:
    """Find a shortest violation or prove safety in the finite union-flow model.

    A shortest violating trace may be assumed to have only strict transitions:
    removing a no-op leaves the state and all later memoryless guard decisions
    unchanged.  Because every strict union-flow transition sets at least one
    previously false ``(location, label)`` bit, no shortest counterexample is
    longer than the number of initially false state bits.  Exhausting that
    bound therefore proves ``PASS`` for this restricted model.

    ``max_depth`` is an engineering budget.  If it is lower than the complete
    bound and no violation is found, the result is ``UNKNOWN`` rather than
    ``PASS``.
    """
    started = perf_counter()
    constraints = tuple(constraints)

    if model.enabled_fn is not None:
        raise SymbolicBMCUnsupported(
            "symbolic BMC currently supports only default declarative enablement"
        )

    locations, labels = _ordered_domain(model, policy, initial_state, constraints)
    bits = tuple((location, label) for location in locations for label in labels)
    bit_index = {bit: index for index, bit in enumerate(bits)}
    initial_true = sum(
        1 for location, label in bits if label in initial_state.get(location)
    )
    complete_bound = len(bits) - initial_true
    requested_depth = complete_bound if max_depth is None else max_depth
    if requested_depth < 0:
        raise ValueError("max_depth must be non-negative or None")

    if not is_safe(initial_state, policy):
        cex = Counterexample(
            trace=(),
            final_state=initial_state,
            violations=find_violations(initial_state, policy),
            last_event=None,
        )
        return SymbolicBMCResult(
            status="FAIL",
            counterexample=cex,
            state_bits=len(bits),
            action_count=len(model.actions),
            depth_bound=complete_bound,
            checked_depth=0,
            solver_calls=0,
            elapsed_seconds=perf_counter() - started,
        )

    if not model.actions or complete_bound == 0:
        status = "PASS" if requested_depth >= complete_bound else "UNKNOWN"
        return SymbolicBMCResult(
            status=status,
            counterexample=None,
            state_bits=len(bits),
            action_count=len(model.actions),
            depth_bound=complete_bound,
            checked_depth=0,
            solver_calls=0,
            elapsed_seconds=perf_counter() - started,
            reason="complete strict-transition bound exhausted" if status == "PASS" else "depth budget exhausted",
        )

    solver = z3.Solver()
    if timeout_ms is not None:
        if timeout_ms < 1:
            raise ValueError("timeout_ms must be positive or None")
        solver.set(timeout=timeout_ms)

    states: List[List[z3.BoolRef]] = []
    choices: List[List[z3.BoolRef]] = []

    def make_state_vars(depth: int) -> List[z3.BoolRef]:
        return [z3.Bool(f"x_{depth}_{index}") for index in range(len(bits))]

    def eta_expr(state_vars: Sequence[z3.BoolRef], action: ConcreteAction, label: Label) -> z3.BoolRef:
        terms: List[z3.BoolRef] = [z3.BoolVal(label in action.gen)]
        terms.extend(state_vars[bit_index[(location, label)]] for location in action.reads)
        return z3.Or(terms)

    def deny_expr(state_vars: Sequence[z3.BoolRef], action: ConcreteAction) -> z3.BoolRef:
        terms: List[z3.BoolRef] = []
        for constraint in constraints:
            if _matches(constraint, action):
                terms.extend(
                    eta_expr(state_vars, action, label)
                    for label in constraint.forbidden_labels
                )
        return z3.Or(terms) if terms else z3.BoolVal(False)

    def bad_expr(state_vars: Sequence[z3.BoolRef]) -> z3.BoolRef:
        terms = [
            state_vars[bit_index[(location, label)]]
            for location in policy.locations()
            for label in policy.forbidden(location)
        ]
        return z3.Or(terms) if terms else z3.BoolVal(False)

    states.append(make_state_vars(0))
    for index, (location, label) in enumerate(bits):
        solver.add(states[0][index] == (label in initial_state.get(location)))

    def add_step(depth: int) -> None:
        current = states[depth]
        post = make_state_vars(depth + 1)
        states.append(post)
        step_choices = [z3.Bool(f"choose_{depth}_{index}") for index in range(len(model.actions))]
        choices.append(step_choices)
        solver.add(z3.PbEq([(choice, 1) for choice in step_choices], 1))

        for action_index, action in enumerate(model.actions):
            choice = step_choices[action_index]
            solver.add(z3.Implies(choice, z3.Not(deny_expr(current, action))))

            changed: List[z3.BoolRef] = []
            for bit, (location, label) in enumerate(bits):
                if location in action.writes:
                    next_value = z3.Or(current[bit], eta_expr(current, action, label))
                else:
                    next_value = current[bit]
                solver.add(z3.Implies(choice, post[bit] == next_value))
                changed.append(post[bit] != current[bit])

            # No-op steps can be removed from a shortest counterexample because
            # actions and guards are history-free in the v2 model.
            solver.add(z3.Implies(choice, z3.Or(changed)))

    def materialize_state(z3_model: z3.ModelRef, depth: int) -> TaintState:
        mapping = {}
        for location in locations:
            present = {
                label
                for label in labels
                if z3.is_true(z3_model.eval(states[depth][bit_index[(location, label)]], model_completion=True))
            }
            if present:
                mapping[location] = present
        return make_state(mapping)

    def counterexample_from_model(z3_model: z3.ModelRef, depth: int) -> Counterexample:
        trace_steps: List[Step] = []
        current = initial_state
        for step_index in range(depth):
            selected = next(
                index
                for index, choice in enumerate(choices[step_index])
                if z3.is_true(z3_model.eval(choice, model_completion=True))
            )
            action = model.actions[selected]
            post = execute(current, action)
            trace_steps.append(
                Step(
                    index=step_index,
                    state=current,
                    action=action,
                    event_taint=event_taint(current, action),
                    post_state=post,
                )
            )
            current = post

        last = trace_steps[-1]
        return Counterexample(
            trace=tuple(trace_steps),
            final_state=current,
            violations=find_violations(current, policy),
            last_event=LastEvent(
                state=last.state,
                action=last.action,
                event_taint=last.event_taint,
            ),
        )

    solver_calls = 0
    checked_depth = 0
    for depth in range(1, requested_depth + 1):
        add_step(depth - 1)
        solver.push()
        solver.add(bad_expr(states[depth]))
        result = solver.check()
        solver_calls += 1
        checked_depth = depth

        if result == z3.sat:
            cex = counterexample_from_model(solver.model(), depth)
            solver.pop()
            return SymbolicBMCResult(
                status="FAIL",
                counterexample=cex,
                state_bits=len(bits),
                action_count=len(model.actions),
                depth_bound=complete_bound,
                checked_depth=checked_depth,
                solver_calls=solver_calls,
                elapsed_seconds=perf_counter() - started,
            )

        solver.pop()
        if result == z3.unknown:
            return SymbolicBMCResult(
                status="UNKNOWN",
                counterexample=None,
                state_bits=len(bits),
                action_count=len(model.actions),
                depth_bound=complete_bound,
                checked_depth=checked_depth,
                solver_calls=solver_calls,
                elapsed_seconds=perf_counter() - started,
                reason=solver.reason_unknown(),
            )

    status = "PASS" if requested_depth >= complete_bound else "UNKNOWN"
    return SymbolicBMCResult(
        status=status,
        counterexample=None,
        state_bits=len(bits),
        action_count=len(model.actions),
        depth_bound=complete_bound,
        checked_depth=checked_depth,
        solver_calls=solver_calls,
        elapsed_seconds=perf_counter() - started,
        reason="complete strict-transition bound exhausted" if status == "PASS" else "depth budget exhausted",
    )
