"""
@function      :
@time          :2026/8/3 15:22
"""
# sage/model.py

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterable, Mapping, Optional, Tuple


# =============================================================================
# 基础类型别名
# =============================================================================

Label = str
AgentId = str
ToolId = str

ParamKey = str
ParamValue = Any
Params = Mapping[ParamKey, ParamValue]
ParamsItems = Tuple[Tuple[ParamKey, ParamValue], ...]

# 注意：这里 LabelSet 是类型别名，运行时本质是 frozenset[Label]
LabelSet = frozenset[Label]


# =============================================================================
# Definition 2: 位置 V = Ctx ⊎ Slot
# =============================================================================

class LocationKind(str, Enum):
    CTX = "ctx"
    SLOT = "slot"

@dataclass(frozen=True)
class Location:
    """
    位置对象。

    两类位置：
    - ctx(agent): Agent 上下文；
    - slot(resource, slot_name): 共享资源槽位。
    """

    kind: LocationKind
    agent: Optional[AgentId] = None
    resource: Optional[str] = None
    slot_name: Optional[str] = None  # <--- 重命名，避免与方法名冲突

    def __post_init__(self) -> None:
        if self.kind == LocationKind.CTX:
            if self.agent is None:
                raise ValueError("ctx location requires agent")
            if self.resource is not None or self.slot_name is not None:
                raise ValueError("ctx location cannot have resource/slot")
        elif self.kind == LocationKind.SLOT:
            if self.resource is None:
                raise ValueError("slot location requires resource")
        else:
            raise ValueError(f"unknown location kind: {self.kind}")

    @staticmethod
    def ctx(agent: AgentId) -> "Location":
        return Location(kind=LocationKind.CTX, agent=agent)

    @staticmethod
    def slot(resource: str, slot_name: Optional[str] = None) -> "Location":
        return Location(kind=LocationKind.SLOT, resource=resource, slot_name=slot_name)

    def canonical(self) -> str:
        if self.kind == LocationKind.CTX:
            return f"ctx:{self.agent}"
        if self.slot_name is None:
            return f"slot:{self.resource}"
        return f"slot:{self.resource}.{self.slot_name}"

    def __str__(self) -> str:
        return self.canonical()


# =============================================================================
# Definition 3: 系统状态 x: V -> 2^L
# =============================================================================

@dataclass(frozen=True)
class TaintState:
    """
    不可变污点状态。

    内部用 tuple 存储非空污点位置，以保证 hash 和不可变性。
    """

    _items: Tuple[Tuple[Location, LabelSet], ...]
    _map: Optional[Mapping[Location, LabelSet]] = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
        hash=False,
    )

    def __post_init__(self) -> None:
        mapping = {loc: frozenset(labels) for loc, labels in self._items}
        object.__setattr__(self, "_map", mapping)

    def get(self, loc: Location) -> LabelSet:
        assert self._map is not None
        return self._map.get(loc, frozenset())

    def locations(self) -> Iterable[Location]:
        assert self._map is not None
        return self._map.keys()

    def items(self) -> Iterable[Tuple[Location, LabelSet]]:
        assert self._map is not None
        return self._map.items()

    def is_empty(self) -> bool:
        assert self._map is not None
        return len(self._map) == 0

    def canonical(self) -> str:
        parts = []
        for loc, labels in sorted(self.items(), key=lambda kv: str(kv[0])):
            parts.append(f"{loc}={{{','.join(sorted(labels))}}}")
        return "State(" + "; ".join(parts) + ")"

    def __str__(self) -> str:
        return self.canonical()


def make_state(mapping: Mapping[Location, Iterable[Label]]) -> TaintState:
    """
    从普通 mapping 构造不可变 TaintState。

    空标签集合会被过滤掉。
    """
    normalized = []
    for loc, labels in mapping.items():
        label_set = frozenset(labels)
        if label_set:
            normalized.append((loc, label_set))

    normalized.sort(key=lambda kv: str(kv[0]))
    return TaintState(tuple(normalized))


# =============================================================================
# Definition 4: 具体动作 u = (a, t, p)
# =============================================================================

@dataclass(frozen=True)
class ConcreteAction:
    """
    参数化具体动作。

    这里要求 Rd/Wr/Gen 已经在参数解析后确定。
    """

    agent: AgentId
    tool: ToolId
    _params: ParamsItems
    reads: frozenset[Location]
    writes: frozenset[Location]
    gen: LabelSet

    @property
    def params_items(self) -> ParamsItems:
        return self._params

    @property
    def params(self) -> dict:
        return dict(self._params)

    def canonical(self) -> str:
        params_str = ",".join(f"{k}={v!r}" for k, v in self._params)
        return f"{self.agent}/{self.tool}({params_str})"

    def __str__(self) -> str:
        return self.canonical()


def make_action(
    agent: AgentId,
    tool: ToolId,
    params: Params,
    reads: Iterable[Location],
    writes: Iterable[Location],
    gen: Iterable[Label] = (),
) -> ConcreteAction:
    """
    构造具体动作。

    params 会被排序，保证相同参数具有稳定哈希。
    """
    params_items = tuple(sorted(params.items(), key=lambda kv: str(kv[0])))
    return ConcreteAction(
        agent=agent,
        tool=tool,
        _params=params_items,
        reads=frozenset(reads),
        writes=frozenset(writes),
        gen=frozenset(gen),
    )


# =============================================================================
# 有限工具转移模型 M
# =============================================================================

@dataclass(frozen=True)
class ToolModel:
    """
    有限工具转移模型 M。

    当前版本假设：
    - Agent、Tool、Location、Label、Action 都有限；
    - 每个 ConcreteAction 的 Rd/Wr/Gen 已解析；
    - enabled 可通过可选 enabled_fn 表达，否则默认允许。
    """

    agents: frozenset[AgentId]
    tools: frozenset[ToolId]
    locations: frozenset[Location]
    labels: frozenset[Label]
    actions: Tuple[ConcreteAction, ...]
    enabled_fn: Optional[Callable[[TaintState, ConcreteAction], bool]] = field(
        default=None,
        compare=False,
        hash=False,
    )

    def enabled(self, state: TaintState, action: ConcreteAction) -> bool:
        if action.agent not in self.agents:
            return False
        if action.tool not in self.tools:
            return False
        if self.enabled_fn is None:
            return True
        return bool(self.enabled_fn(state, action))


# =============================================================================
# Definition 7: 禁止流策略 B: V -> 2^L
# =============================================================================

@dataclass(frozen=True)
class ForbiddenFlowPolicy:
    """
    禁止流策略 B。

    B(v) 是禁止出现在位置 v 的来源标签集合。
    """

    _items: Tuple[Tuple[Location, LabelSet], ...]
    _map: Optional[Mapping[Location, LabelSet]] = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
        hash=False,
    )

    def __post_init__(self) -> None:
        mapping = {loc: frozenset(labels) for loc, labels in self._items}
        object.__setattr__(self, "_map", mapping)

    def forbidden(self, loc: Location) -> LabelSet:
        assert self._map is not None
        return self._map.get(loc, frozenset())

    def locations(self) -> Iterable[Location]:
        assert self._map is not None
        return self._map.keys()

    def canonical(self) -> str:
        parts = []
        assert self._map is not None
        for loc, labels in sorted(self._map.items(), key=lambda kv: str(kv[0])):
            parts.append(f"{loc}<-{{{','.join(sorted(labels))}}}")
        return "Policy(" + "; ".join(parts) + ")"

    def __str__(self) -> str:
        return self.canonical()


def make_policy(mapping: Mapping[Location, Iterable[Label]]) -> ForbiddenFlowPolicy:
    """
    构造禁止流策略。
    """
    normalized = []
    for loc, labels in mapping.items():
        label_set = frozenset(labels)
        if label_set:
            normalized.append((loc, label_set))

    normalized.sort(key=lambda kv: str(kv[0]))
    return ForbiddenFlowPolicy(tuple(normalized))
