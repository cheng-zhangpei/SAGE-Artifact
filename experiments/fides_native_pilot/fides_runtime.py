"""Offline subset of the public FIDES tutorial policy runtime.

The shapes and enforcement convention follow microsoft/fides Tutorial.ipynb at
commit 669c046c4adbc56ee49c9672fdd30c54937ea062: a policy consumes a labeled
action trace and raises PolicyViolation before the tool effect.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import FrozenSet, Generic, TypeVar

@dataclass
class Action:
    pass

@dataclass
class ToolCall(Action):
    id: str
    name: str
    arguments: str

class PolicyViolation(Exception):
    def __init__(self, reason: str):
        super().__init__(f"Policy violation: {reason}")
        self.reason = reason

T = TypeVar("T")
class PowersetLattice(Generic[T]):
    def __init__(self, subset: FrozenSet[T], universe: FrozenSet[T]):
        if not subset.issubset(universe):
            raise ValueError("Subset must be within the universe.")
        self.subset, self.universe = subset, universe
    def leq(self, other): return self.subset.issubset(other.subset)
    def join(self, other): return PowersetLattice(self.subset | other.subset, self.universe)
    def meet(self, other): return PowersetLattice(self.subset & other.subset, self.universe)
    def __le__(self, other): return self.leq(other)
    def __repr__(self): return f"Powerset({{{', '.join(map(str, self.subset))}}})"

def enforce(policy, action: ToolCall, labels: FrozenSet[str], universe: FrozenSet[str]) -> bool:
    """Return True iff the policy rejects before the tool effect."""
    try:
        policy([(action, PowersetLattice(labels, universe))])
        return False
    except PolicyViolation:
        return True
