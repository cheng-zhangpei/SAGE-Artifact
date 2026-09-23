from __future__ import annotations

from integrations.supportdesk.monitor import (
    ContextOnlyMonitor,
    SAGEReferenceMonitor,
    supportdesk_policy,
)
from integrations.supportdesk.run_experiment import run_integration
from integrations.supportdesk.system import LocalCaptureServer, SupportDeskSystem
from integrations.supportdesk.workflows import WORKFLOWS
from sage.v2.semantics import deny_star


def _workflow(workflow_id):
    return next(item for item in WORKFLOWS if item.workflow_id == workflow_id)


def _monitors(system):
    # Pair workflows override fixtures that are intentionally absent from the
    # default SupportDesk state.  Resolve every declared action against its own
    # fresh fixture, matching the experiment runner and keeping this helper
    # independent of workflow order.
    invocations = []
    for workflow in WORKFLOWS:
        system.reset(
            log_overrides=workflow.log_overrides,
            ticket_overrides=workflow.ticket_overrides,
        )
        invocations.append(system.resolve(workflow.tool, workflow.params))
    system.reset()
    policy = supportdesk_policy()
    return (
        ContextOnlyMonitor(policy),
        SAGEReferenceMonitor(
            (invocation.action for invocation in invocations), policy
        ),
    )


def test_workflow_catalog_is_large_and_predeclared():
    assert len(WORKFLOWS) >= 15
    assert len({workflow.workflow_id for workflow in WORKFLOWS}) == len(WORKFLOWS)


def test_same_invocation_gap_is_real_file_read(tmp_path):
    with LocalCaptureServer() as capture:
        system = SupportDeskSystem(tmp_path, capture)
        workflow = _workflow("W02_pii_log_external")
        invocation = system.resolve(workflow.tool, workflow.params)
        state = system.taint_state()
        context, sage = _monitors(system)

        assert state.get(next(loc for loc in invocation.action.reads if str(loc) == "ctx:support")) == frozenset()
        assert system.shared_log("pii")[1] == frozenset({"PII"})
        assert context.decide(state, invocation.action).denied is False
        assert sage.decide(state, invocation.action).denied is True


def test_allowed_external_call_performs_real_loopback_http(tmp_path):
    with LocalCaptureServer() as capture:
        system = SupportDeskSystem(tmp_path, capture)
        workflow = _workflow("W01_clean_log_external")
        invocation = system.resolve(workflow.tool, workflow.params)
        _, sage = _monitors(system)

        assert sage.decide(system.taint_state(), invocation.action).denied is False
        system.execute(invocation)
        assert len(capture.records) == 1
        assert capture.records[0]["body"]["body"] == "worker completed normally"


def test_denied_multiwrite_has_zero_side_effects(tmp_path):
    with LocalCaptureServer() as capture:
        system = SupportDeskSystem(tmp_path, capture)
        workflow = _workflow("W12_multiwrite_pii")
        invocation = system.resolve(workflow.tool, workflow.params)
        _, sage = _monitors(system)
        before = system.snapshot()

        assert sage.decide(system.taint_state(), invocation.action).denied is True
        after = system.snapshot()
        assert before == after
        assert capture.records == []


def test_sanitizer_exposes_a_declared_model_fidelity_limit(tmp_path):
    with LocalCaptureServer() as capture:
        system = SupportDeskSystem(tmp_path, capture)
        workflow = _workflow("W15_sanitized_pii_summary")
        invocation = system.resolve(workflow.tool, workflow.params)
        _, sage = _monitors(system)
        state = system.taint_state()

        assert invocation.physical_dangerous is False
        assert deny_star(state, invocation.action, sage.policy) is True
        assert sage.decide(state, invocation.action).denied is True


def test_complete_integration_metrics(tmp_path):
    result = run_integration(tmp_path)
    metrics = {row["monitor"]: row for row in result["runtime_monitor_metrics"]}

    assert result["workflow_count"] >= 15
    assert len(result["decision_records"]) == 2 * result["workflow_count"]
    assert metrics["context_only"]["physical_DER"] < 1.0
    assert metrics["context_only"]["physical_violations_allowed"] > 0
    assert metrics["sage"]["physical_DER"] == 1.0
    assert metrics["sage"]["model_DER"] == 1.0
    assert metrics["sage"]["model_BBR"] == 0.0
    assert metrics["sage"]["denied_zero_side_effect"] is True
    assert result["model_fidelity"]["mismatches"] == [
        "W15_sanitized_pii_summary"
    ]
