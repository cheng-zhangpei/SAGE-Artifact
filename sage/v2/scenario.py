"""
@function      :
@time          :2026/8/3 15:42
"""
# sage/v2/scenario.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Tuple

from .guards import Constraint, ParamFilter
from .model import (
    ConcreteAction,
    ForbiddenFlowPolicy,
    Location,
    TaintState,
    ToolModel,
    make_action,
    make_policy,
    make_state,
)


def parse_location(ref: str) -> Location:
    """
    支持两种位置字符串：

    - ctx:agent_name
    - slot:resource_name
    - slot:resource_name.slot_name
    """

    if ref.startswith("ctx:"):
        agent = ref[len("ctx:"):]
        if not agent:
            raise ValueError("ctx location reference requires agent name")
        return Location.ctx(agent)

    if ref.startswith("slot:"):
        rest = ref[len("slot:"):]
        if not rest:
            raise ValueError("slot location reference requires resource name")

        if "." in rest:
            resource, slot = rest.split(".", 1)
            if not resource:
                raise ValueError("slot location reference requires non-empty resource")
            return Location.slot(resource, slot if slot else None)

        return Location.slot(rest)

    raise ValueError(f"invalid location reference: {ref!r}")


def params_items_from_dict(params: Mapping[str, Any]) -> Tuple[Tuple[str, Any], ...]:
    return tuple(sorted(params.items(), key=lambda kv: str(kv[0])))


@dataclass(frozen=True)
class Scenario:
    model: ToolModel
    policy: ForbiddenFlowPolicy
    initial_state: TaintState
    constraints: Tuple[Constraint, ...]


def build_scenario(spec: Mapping[str, Any]) -> Scenario:
    """
    用户场景输入格式：

    {
        "agents": [...],
        "tools": [...],
        "labels": [...],
        "locations": ["ctx:a", "slot:file.T1", ...],
        "actions": [
            {
                "agent": "support",
                "tool": "send_file",
                "params": {"file": "T1", "channel": "external"},
                "reads": ["ctx:support", "slot:file.T1"],
                "writes": ["slot:external.slack"],
                "gen": ["PII"]
            }
        ],
        "policy": {
            "slot:external.slack": ["PII"]
        },
        "initial_state": {
            "slot:file.T1": ["PII"]
        },
        "constraints": [
            {
                "agent": "support",
                "tool": "send_file",
                "params": {"file": "T1", "channel": "external"},
                "forbidden_labels": ["PII"]
            }
        ]
    }

    注意：
    - constraint 必须显式提供 params、wildcard_params 或 match_all=true；
    - 默认不允许可疑通配，避免用户无意中过约束。
    """

    agents = set(spec.get("agents", []))
    tools = set(spec.get("tools", []))
    labels = set(spec.get("labels", []))
    locations = set()

    def add_location_ref(ref: str) -> Location:
        loc = parse_location(ref)
        locations.add(loc)
        return loc

    for ref in spec.get("locations", []):
        add_location_ref(ref)

    actions = []

    for action_spec in spec.get("actions", []):
        agent = action_spec["agent"]
        tool = action_spec["tool"]
        params = action_spec.get("params", {})

        agents.add(agent)
        tools.add(tool)

        reads = set()
        writes = set()

        for ref in action_spec.get("reads", []):
            reads.add(add_location_ref(ref))

        for ref in action_spec.get("writes", []):
            writes.add(add_location_ref(ref))

        gen = frozenset(action_spec.get("gen", []))
        labels.update(gen)

        # Agent 的 ctx 位置默认加入模型，即使动作没有显式读取它。
        # 这样 observation_ctx 和状态查询更稳定。
        ctx_loc = Location.ctx(agent)
        locations.add(ctx_loc)

        action = make_action(
            agent=agent,
            tool=tool,
            params=params,
            reads=reads,
            writes=writes,
            gen=gen,
        )
        actions.append(action)

    policy_mapping = {}

    for loc_ref, loc_labels in spec.get("policy", {}).items():
        loc = add_location_ref(loc_ref)
        label_set = set(loc_labels)
        labels.update(label_set)
        policy_mapping[loc] = label_set

    policy = make_policy(policy_mapping)

    initial_mapping = {}

    for loc_ref, loc_labels in spec.get("initial_state", {}).items():
        loc = add_location_ref(loc_ref)
        label_set = set(loc_labels)
        labels.update(label_set)
        initial_mapping[loc] = label_set

    initial_state = make_state(initial_mapping)

    locations.update(policy.locations())
    locations.update(initial_state.locations())

    constraints = []

    for constraint_spec in spec.get("constraints", []):
        agent = constraint_spec["agent"]
        tool = constraint_spec["tool"]
        forbidden_labels = frozenset(constraint_spec.get("forbidden_labels", []))
        labels.update(forbidden_labels)

        if "params" in constraint_spec:
            param_filter = ParamFilter(
                exact_patterns=(
                    params_items_from_dict(constraint_spec["params"]),
                ),
                wildcard_patterns=(),
                match_all=False,
            )
        elif "wildcard_params" in constraint_spec:
            param_filter = ParamFilter(
                exact_patterns=(),
                wildcard_patterns=(
                    params_items_from_dict(constraint_spec["wildcard_params"]),
                ),
                match_all=False,
            )
        elif constraint_spec.get("match_all", False):
            param_filter = ParamFilter(
                exact_patterns=(),
                wildcard_patterns=(),
                match_all=True,
            )
        else:
            raise ValueError(
                "constraint must contain 'params', 'wildcard_params', "
                "or explicit 'match_all': true"
            )

        constraint = Constraint(
            agent=agent,
            tool=tool,
            param_filter=param_filter,
            forbidden_labels=forbidden_labels,
            name=constraint_spec.get("name", "user_constraint"),
        )
        constraints.append(constraint)

    model = ToolModel(
        agents=frozenset(agents),
        tools=frozenset(tools),
        locations=frozenset(locations),
        labels=frozenset(labels),
        actions=tuple(actions),
    )

    return Scenario(
        model=model,
        policy=policy,
        initial_state=initial_state,
        constraints=tuple(constraints),
    )
