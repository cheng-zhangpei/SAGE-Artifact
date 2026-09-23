"""Cross-check the new symbolic backend against the reference BFS."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sage.v2.counterexample import shortest_counterexample
from sage.v2.coverage import certify_action_coverage
from sage.v2.scenario import build_scenario
from sage.v2.symbolic_bmc import verify_symbolic_bmc
from sage.v2.synthesis import direct_sage


def _scenario(name: str):
    root = Path(__file__).resolve().parents[3]
    with (root / "experiments" / "scenarios" / name / "scenario.json").open(
        "r", encoding="utf-8"
    ) as handle:
        return build_scenario(json.load(handle))


@pytest.mark.parametrize("name", ["s1_full", "s2_full", "s3_full", "s4_full"])
def test_symbolic_bmc_matches_reference_bfs_on_small_scenarios(name: str):
    scenario = _scenario(name)
    bfs = shortest_counterexample(
        scenario.model,
        scenario.policy,
        scenario.constraints,
        scenario.initial_state,
        max_states=10_000,
    )
    symbolic = verify_symbolic_bmc(
        scenario.model,
        scenario.policy,
        scenario.constraints,
        scenario.initial_state,
        timeout_ms=10_000,
    )

    assert symbolic.status == ("FAIL" if bfs is not None else "PASS")
    assert (symbolic.counterexample is None) == (bfs is None)
    if bfs is not None:
        assert symbolic.counterexample is not None
        assert len(symbolic.counterexample.trace) == len(bfs.trace)


@pytest.mark.parametrize("name", ["s1_full", "s2_full", "s3_full", "s4_full"])
def test_symbolic_bmc_agrees_with_bfs_for_direct_sage(name: str):
    scenario = _scenario(name)
    guards = direct_sage(scenario.model, scenario.policy)
    bfs = shortest_counterexample(
        scenario.model,
        scenario.policy,
        guards,
        scenario.initial_state,
        max_states=10_000,
    )
    symbolic = verify_symbolic_bmc(
        scenario.model,
        scenario.policy,
        guards,
        scenario.initial_state,
        timeout_ms=10_000,
    )

    assert bfs is None
    assert symbolic.status == "PASS"
    assert symbolic.counterexample is None


def test_depth_budget_never_claims_pass():
    scenario = _scenario("s1_full")
    symbolic = verify_symbolic_bmc(
        scenario.model,
        scenario.policy,
        direct_sage(scenario.model, scenario.policy),
        scenario.initial_state,
        max_depth=0,
    )

    assert symbolic.status == "UNKNOWN"


@pytest.mark.parametrize("name", ["s1_full", "s2_full", "s3_full", "s4_full"])
def test_complete_direct_sage_coverage_is_a_safety_certificate(name: str):
    scenario = _scenario(name)
    certificate = certify_action_coverage(
        scenario.model,
        scenario.policy,
        direct_sage(scenario.model, scenario.policy),
    )

    assert certificate.safe
    assert not certificate.gaps


def test_empty_candidate_has_coverage_gaps():
    scenario = _scenario("s1_full")
    certificate = certify_action_coverage(
        scenario.model,
        scenario.policy,
        (),
    )

    assert not certificate.safe
    assert certificate.gaps
