"""A search-free sufficient safety certificate for concrete guard coverage.

The certificate is intentionally one-sided.  A complete cover proves safety
for the finite union-flow model; a gap only says that a reachability backend is
still needed, because upstream guards may make the missing event unreachable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

from .guards import Constraint
from .model import ConcreteAction, ForbiddenFlowPolicy, LabelSet, ToolModel
from .semantics import forbidden_targets_of_action


@dataclass(frozen=True)
class CoverageGap:
    action: ConcreteAction
    required_labels: LabelSet
    covered_labels: LabelSet
    missing_labels: LabelSet


@dataclass(frozen=True)
class CoverageCertificate:
    safe: bool
    gaps: Tuple[CoverageGap, ...]


def _matches(constraint: Constraint, action: ConcreteAction) -> bool:
    return (
        constraint.agent == action.agent
        and constraint.tool == action.tool
        and constraint.param_filter.match(action.params)
    )


def certify_action_coverage(
    model: ToolModel,
    policy: ForbiddenFlowPolicy,
    constraints: Iterable[Constraint],
) -> CoverageCertificate:
    """Prove safety when every concrete dangerous label is denied locally.

    For a concrete action ``u``, any unsafe successor from a safe state has an
    event label in ``Q_B(u)``.  If every label in ``Q_B(u)`` appears in a
    candidate clause matching ``u``, that same clause rejects the event.  By
    the one-step danger characterization, complete coverage therefore implies
    trace safety under complete mediation and an initially safe state.
    """
    constraints = tuple(constraints)
    gaps = []

    for action in model.actions:
        required = forbidden_targets_of_action(policy, action)
        if not required:
            continue
        covered = frozenset(
            label
            for constraint in constraints
            if _matches(constraint, action)
            for label in constraint.forbidden_labels
        )
        missing = frozenset(required - covered)
        if missing:
            gaps.append(
                CoverageGap(
                    action=action,
                    required_labels=required,
                    covered_labels=covered,
                    missing_labels=missing,
                )
            )

    return CoverageCertificate(safe=not gaps, gaps=tuple(gaps))
