from __future__ import annotations
"""
@function      :
@time          :2026/8/17 11:26
"""
"""
benchmarks/context_invisible/baselines.py

Canonical baselines for the Context-Invisible IFC Benchmark.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

from sage.v2.model import ConcreteAction, Location, TaintState, ToolModel, ForbiddenFlowPolicy
from sage.v2.semantics import event_taint, forbidden_targets_of_action


@dataclass(frozen=True)
class EventRecord:
    """One resolved event (state, action) with precomputed fields."""
    case_id: str
    state: TaintState
    action: ConcreteAction
    eta: frozenset  # event taint
    q_b: frozenset  # target-forbidden labels
    is_dangerous: bool

    @property
    def o_ctx(self) -> Tuple:
        """O_ctx = (agent, tool, params, x(ctx(agent)))"""
        ctx_loc = Location.ctx(self.action.agent)
        ctx_labels = frozenset(self.state.get(ctx_loc))
        return (
            self.action.agent,
            self.action.tool,
            self.action.params_items,
            ctx_labels,
        )

    @property
    def o_event(self) -> Tuple:
        """O_event = (agent, tool, params, eta_u(x))"""
        return (
            self.action.agent,
            self.action.tool,
            self.action.params_items,
            self.eta,
        )


def build_event_records(cases: List[dict]) -> List[EventRecord]:
    """
    From a list of loaded cases (each with 'scenario' and 'oracle'),
    build EventRecord objects for the target action.
    """
    from sage.v2.scenario import build_scenario

    records = []
    for case in cases:
        scenario = case["scenario"]
        oracle = case["oracle"]
        target_spec = oracle["target_action"]

        # Find target action in model
        action = None
        for a in scenario.model.actions:
            if (a.agent == target_spec["agent"]
                    and a.tool == target_spec["tool"]
                    and dict(a.params) == target_spec["params"]):
                action = a
                break
        if action is None:
            raise ValueError(f"Target action not found: {target_spec}")

        eta = event_taint(scenario.initial_state, action)
        q_b = forbidden_targets_of_action(scenario.policy, action)
        is_dangerous = bool(eta & q_b)

        case_id = f"{oracle['pair_id']}_{oracle['class']}"
        records.append(EventRecord(
            case_id=case_id,
            state=scenario.initial_state,
            action=action,
            eta=eta,
            q_b=q_b,
            is_dangerous=is_dangerous,
        ))
    return records


def sage_decision(record: EventRecord) -> str:
    """SAGE pre-commit decision: DENY iff eta ∩ Q_B ≠ ∅"""
    return "DENY" if record.is_dangerous else "ALLOW"


def canonical_ctx_only_decisions(records: List[EventRecord]) -> Dict[str, str]:
    """
    Canonical context-only controller (information-theoretic optimum).

    Groups events by O_ctx equivalence class.
    If ANY event in a class is dangerous, DENY the entire class.
    This is the strongest possible safe controller under O_ctx.
    """
    # Group by O_ctx
    obs_classes: Dict[Tuple, List[EventRecord]] = {}
    for r in records:
        key = r.o_ctx
        if key not in obs_classes:
            obs_classes[key] = []
        obs_classes[key].append(r)

    # Decide per class
    decisions = {}
    for key, class_records in obs_classes.items():
        has_danger = any(r.is_dangerous for r in class_records)
        verdict = "DENY" if has_danger else "ALLOW"
        for r in class_records:
            decisions[r.case_id] = verdict
    return decisions


def allow_all_decisions(records: List[EventRecord]) -> Dict[str, str]:
    return {r.case_id: "ALLOW" for r in records}


def deny_all_decisions(records: List[EventRecord]) -> Dict[str, str]:
    return {r.case_id: "DENY" for r in records}


def tool_wide_deny_decisions(records: List[EventRecord]) -> Dict[str, str]:
    """
    Tool-wide taint deny: if ANY event carrying taint targets this tool, deny all.
    Used as Category C baseline (over-blocking comparison).
    """
    # Find tools that have any dangerous event
    dangerous_tools = set()
    for r in records:
        if r.is_dangerous:
            dangerous_tools.add((r.action.agent, r.action.tool))

    decisions = {}
    for r in records:
        if (r.action.agent, r.action.tool) in dangerous_tools:
            decisions[r.case_id] = "DENY"
        else:
            decisions[r.case_id] = "ALLOW"
    return decisions
