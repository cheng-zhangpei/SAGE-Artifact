"""
@function      :
@time          :2026/8/3 15:22
"""
# sage/__init__.py

from .model import (
    AgentId,
    ConcreteAction,
    ForbiddenFlowPolicy,
    Label,
    LabelSet,
    Location,
    LocationKind,
    Params,
    ParamsItems,
    TaintState,
    ToolId,
    ToolModel,
    make_action,
    make_policy,
    make_state,
)

from .semantics import (
    deny_star,
    event_taint,
    execute,
    forbidden_targets_of_action,
    is_bad,
    is_safe,
    one_step_safe,
)

from .guards import (
    Constraint,
    ParamFilter,
    allow_constraints,
    deny_constraints,
    semantic_normalize,
)

from .synthesis import direct_sage

from .counterexample import (
    Counterexample,
    SearchLimitExceeded,
    Step,
    counterexample_to_llm_json,
    find_violations,
    shortest_counterexample,
    trace_safe,
)

from .properties import (
    Event,
    ObservationFn,
    bad_upward_closed_instance,
    check_deny_star_equivalence,
    compute_event_domain,
    ideal_controller_allows,
    lemma_1_monotone_instance,
    lemma_3_instance,
    make_observation_hidden,
    observation_collisions,
    observation_ctx,
    observation_event,
    observation_full,
    reachable_states,
    state_leq,
    zero_overconstraint_condition,
)

__all__ = [
    # model
    "AgentId",
    "ConcreteAction",
    "ForbiddenFlowPolicy",
    "Label",
    "LabelSet",
    "Location",
    "LocationKind",
    "Params",
    "ParamsItems",
    "TaintState",
    "ToolId",
    "ToolModel",
    "make_action",
    "make_policy",
    "make_state",

    # semantics
    "deny_star",
    "event_taint",
    "execute",
    "forbidden_targets_of_action",
    "is_bad",
    "is_safe",
    "one_step_safe",

    # guards
    "Constraint",
    "ParamFilter",
    "allow_constraints",
    "deny_constraints",
    "semantic_normalize",

    # synthesis
    "direct_sage",

    # counterexample
    "Counterexample",
    "SearchLimitExceeded",
    "Step",
    "counterexample_to_llm_json",
    "find_violations",
    "shortest_counterexample",
    "trace_safe",

    # properties
    "Event",
    "ObservationFn",
    "bad_upward_closed_instance",
    "check_deny_star_equivalence",
    "compute_event_domain",
    "ideal_controller_allows",
    "lemma_1_monotone_instance",
    "lemma_3_instance",
    "make_observation_hidden",
    "observation_collisions",
    "observation_ctx",
    "observation_event",
    "observation_full",
    "reachable_states",
    "state_leq",
    "zero_overconstraint_condition",
]
