"""Run the local support-desk integration and retain auditable raw results."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import statistics
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from integrations.supportdesk.monitor import (
    ContextOnlyMonitor,
    MonitorDecision,
    SAGEReferenceMonitor,
    supportdesk_policy,
)
from integrations.supportdesk.system import LocalCaptureServer, SupportDeskSystem
from integrations.supportdesk.workflows import WORKFLOWS, Workflow
from sage.v2.model import ConcreteAction, TaintState
from sage.v2.semantics import deny_star, event_taint, forbidden_targets_of_action


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = PROJECT_ROOT / "experiments" / "reports" / "runs"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metric_rows(decisions: list[dict]) -> list[dict]:
    monitors = sorted({row["monitor"] for row in decisions})
    rows = []
    for monitor in monitors:
        subset = [row for row in decisions if row["monitor"] == monitor]
        dangerous = [row for row in subset if row["physical_dangerous"]]
        benign = [row for row in subset if not row["physical_dangerous"]]
        model_dangerous = [row for row in subset if row["model_dangerous"]]
        model_benign = [row for row in subset if not row["model_dangerous"]]
        decision_samples = sorted(
            row["decision_us"] for row in subset if row.get("decision_us") is not None
        )
        row = {
                "monitor": monitor,
                "workflows": len(subset),
                "physical_dangerous": len(dangerous),
                "physical_benign": len(benign),
                "physical_DER": (
                    sum(row["denied"] for row in dangerous) / len(dangerous)
                    if dangerous
                    else None
                ),
                "physical_BBR": (
                    sum(row["denied"] for row in benign) / len(benign)
                    if benign
                    else None
                ),
                "model_dangerous": len(model_dangerous),
                "model_benign": len(model_benign),
                "model_DER": (
                    sum(row["denied"] for row in model_dangerous)
                    / len(model_dangerous)
                    if model_dangerous
                    else None
                ),
                "model_BBR": (
                    sum(row["denied"] for row in model_benign) / len(model_benign)
                    if model_benign
                    else None
                ),
                "physical_violations_allowed": sum(
                    row["physical_dangerous"] and not row["denied"]
                    for row in subset
                ),
                "denied_zero_side_effect": all(
                    row["denied_zero_side_effect"]
                    for row in subset
                    if row["denied"]
                ),
            }
        if decision_samples:
            row.update(
                {
                    "decision_p50_us": statistics.median(decision_samples),
                    "decision_p95_us": decision_samples[
                        min(
                            len(decision_samples) - 1,
                            math.ceil(0.95 * len(decision_samples)) - 1,
                        )
                    ],
                }
            )
        rows.append(row)
    return rows


def static_baselines(workflow_rows: list[dict]) -> list[dict]:
    dangerous_tools = {
        row["tool"] for row in workflow_rows if row["physical_dangerous"]
    }
    dangerous_parameters = {
        (row["tool"], json.dumps(row["params"], sort_keys=True))
        for row in workflow_rows
        if row["physical_dangerous"]
    }
    controllers: dict[str, Callable[[dict], bool]] = {
        "allow_all": lambda _row: False,
        "deny_all": lambda _row: True,
        "tool_blacklist_oracle": lambda row: row["tool"] in dangerous_tools,
        "parameter_blacklist_oracle": lambda row: (
            row["tool"], json.dumps(row["params"], sort_keys=True)
        )
        in dangerous_parameters,
    }
    expanded = []
    for name, controller in controllers.items():
        for row in workflow_rows:
            expanded.append({**row, "monitor": name, "denied": controller(row)})
    return metric_rows(expanded)


def _execute_one(
    system: SupportDeskSystem,
    workflow: Workflow,
    monitor,
) -> dict:
    system.reset(
        log_overrides=workflow.log_overrides,
        ticket_overrides=workflow.ticket_overrides,
    )
    invocation = system.resolve(workflow.tool, workflow.params)
    state = system.taint_state()
    model_dangerous = deny_star(state, invocation.action, monitor.policy)
    if invocation.physical_dangerous != workflow.expected_physical_dangerous:
        raise AssertionError(f"{workflow.workflow_id}: physical oracle mismatch")
    if model_dangerous != workflow.expected_model_dangerous:
        raise AssertionError(f"{workflow.workflow_id}: model oracle mismatch")

    started = time.perf_counter_ns()
    decision: MonitorDecision = monitor.decide(state, invocation.action)
    decision_us = (time.perf_counter_ns() - started) / 1000.0
    before = system.snapshot()
    execution = None
    execution_ms = None
    if not decision.denied:
        execution_started = time.perf_counter_ns()
        execution = system.execute(invocation)
        execution_ms = (time.perf_counter_ns() - execution_started) / 1e6
    after = system.snapshot()
    side_effect = before != after
    denied_zero_side_effect = (not decision.denied) or (not side_effect)
    if decision.denied and side_effect:
        raise AssertionError(f"{workflow.workflow_id}: denied call changed the system")
    if not decision.denied and not side_effect:
        raise AssertionError(f"{workflow.workflow_id}: allowed call had no real effect")

    return {
        "workflow_id": workflow.workflow_id,
        "category": workflow.category,
        "claim": workflow.claim,
        "monitor": monitor.name,
        "tool": workflow.tool,
        "params": dict(workflow.params),
        "reads": sorted(str(location) for location in invocation.action.reads),
        "writes": sorted(str(location) for location in invocation.action.writes),
        "gen": sorted(invocation.action.gen),
        "context_labels": sorted(state.get(next(
            location for location in invocation.action.reads
            if str(location) == f"ctx:{invocation.action.agent}"
        ))),
        "event_labels": sorted(event_taint(state, invocation.action)),
        "target_forbidden_labels": sorted(
            forbidden_targets_of_action(monitor.policy, invocation.action)
        ),
        "physical_output_labels": sorted(invocation.physical_output_labels),
        "physical_dangerous": invocation.physical_dangerous,
        "model_dangerous": model_dangerous,
        "model_fidelity_match": invocation.physical_dangerous == model_dangerous,
        "denied": decision.denied,
        "decision_reason": decision.reason,
        "decision_us": decision_us,
        "side_effect": side_effect,
        "denied_zero_side_effect": denied_zero_side_effect,
        "physical_violation_executed": (
            invocation.physical_dangerous and not decision.denied
        ),
        "external_capture_count": len(system.capture_server.records),
        "execution": execution,
        "execution_ms": execution_ms,
    }


def run_integration(work_root: Path) -> dict:
    with LocalCaptureServer() as capture:
        system = SupportDeskSystem(work_root, capture)
        system.reset()
        invocations = []
        for workflow in WORKFLOWS:
            system.reset(
                log_overrides=workflow.log_overrides,
                ticket_overrides=workflow.ticket_overrides,
            )
            invocations.append(system.resolve(workflow.tool, workflow.params))
        policy = supportdesk_policy()
        monitors = (
            ContextOnlyMonitor(policy),
            SAGEReferenceMonitor(
                (invocation.action for invocation in invocations), policy
            ),
        )
        decisions = [
            _execute_one(system, workflow, monitor)
            for monitor in monitors
            for workflow in WORKFLOWS
        ]

    # Static baselines use the same physical oracle but do not need execution.
    workflow_rows = []
    seen = set()
    for row in decisions:
        if row["workflow_id"] in seen:
            continue
        seen.add(row["workflow_id"])
        workflow_rows.append(
            {
                "workflow_id": row["workflow_id"],
                "tool": row["tool"],
                "params": row["params"],
                "physical_dangerous": row["physical_dangerous"],
                "model_dangerous": row["model_dangerous"],
                "denied_zero_side_effect": True,
            }
        )
    return {
        "workflow_count": len(WORKFLOWS),
        "decision_records": decisions,
        "runtime_monitor_metrics": metric_rows(decisions),
        "static_baseline_metrics": static_baselines(workflow_rows),
        "direct_sage_guard_count": len(monitors[1].guards),
        "model_fidelity": {
            "matches": sum(
                row["model_fidelity_match"]
                for row in decisions
                if row["monitor"] == "sage"
            ),
            "total": len(WORKFLOWS),
            "mismatches": [
                row["workflow_id"]
                for row in decisions
                if row["monitor"] == "sage" and not row["model_fidelity_match"]
            ],
        },
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def markdown_report(result: dict, manifest: dict) -> str:
    metric_by_name = {
        row["monitor"]: row
        for row in [
            *result["static_baseline_metrics"],
            *result["runtime_monitor_metrics"],
        ]
    }
    lines = [
        "# Local support-desk integration result",
        "",
        f"Status: **{manifest['status']}**",
        "",
        f"Workflows: **{result['workflow_count']}**",
        f"DirectSAGE guards: **{result['direct_sage_guard_count']}**",
        f"Model fidelity: **{result['model_fidelity']['matches']}/{result['model_fidelity']['total']}**",
        "",
        "| Monitor | Physical DER | Physical BBR | Violations allowed | Decision p50 | Denied calls side-effect free |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name in (
        "allow_all",
        "deny_all",
        "tool_blacklist_oracle",
        "parameter_blacklist_oracle",
        "context_only",
        "sage",
    ):
        row = metric_by_name[name]
        lines.append(
            f"| {name} | {100 * row['physical_DER']:.1f}% | "
            f"{100 * row['physical_BBR']:.1f}% | "
            f"{row['physical_violations_allowed']} | "
            f"{row.get('decision_p50_us', 0):.2f} us | "
            f"{'yes' if row['denied_zero_side_effect'] else 'no'} |"
        )
    lines.extend(
        [
            "",
            "## Fidelity mismatch",
            "",
            "`W15_sanitized_pii_summary` is physically safe because the trusted tool removes the email, "
            "but the base union-flow semantics conservatively propagates every read label and denies it. "
            "This is an explicit model limitation, not a hidden failure.",
            "",
            "## Real effects",
            "",
            "Allowed external calls performed real HTTP POSTs to a loopback capture server. "
            "Allowed internal calls changed SQLite rows. Every denied call was checked against a "
            "before/after snapshot and produced zero application or network side effects.",
        ]
    )
    return "\n".join(lines) + "\n"


def latex_table(result: dict) -> str:
    metric_by_name = {
        row["monitor"]: row
        for row in [
            *result["static_baseline_metrics"],
            *result["runtime_monitor_metrics"],
        ]
    }
    display_names = {
        "allow_all": "Allow all",
        "deny_all": "Deny all",
        "tool_blacklist_oracle": "Tool BL",
        "parameter_blacklist_oracle": "Param. BL",
        "context_only": "Context",
        "sage": "SAGE",
    }
    lines = [
        r"\begingroup\small",
        r"\setlength{\tabcolsep}{3pt}",
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        r"Monitor & DER & BBR & Vio. & p50 ($\mu$s) \\",
        r"\midrule",
    ]
    for name in (
        "allow_all",
        "deny_all",
        "tool_blacklist_oracle",
        "parameter_blacklist_oracle",
        "context_only",
        "sage",
    ):
        row = metric_by_name[name]
        display = display_names[name]
        latency = (
            f"{row['decision_p50_us']:.2f}"
            if row.get("decision_p50_us") is not None
            else "--"
        )
        lines.append(
            f"{display} & {100 * row['physical_DER']:.1f}\\% & "
            f"{100 * row['physical_BBR']:.1f}\\% & "
            f"{row['physical_violations_allowed']} & {latency} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\endgroup"])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--work-root", type=Path, default=None)
    args = parser.parse_args()
    run_id = datetime.now(timezone.utc).strftime("supportdesk_integration_%Y%m%dT%H%M%SZ")
    output = args.output_root / run_id
    output.mkdir(parents=True, exist_ok=False)

    if args.work_root is None:
        with tempfile.TemporaryDirectory(prefix="sage_supportdesk_") as temporary:
            result = run_integration(Path(temporary))
    else:
        args.work_root.mkdir(parents=True, exist_ok=True)
        result = run_integration(args.work_root)

    context = next(
        row for row in result["runtime_monitor_metrics"] if row["monitor"] == "context_only"
    )
    sage = next(
        row for row in result["runtime_monitor_metrics"] if row["monitor"] == "sage"
    )
    status = "PASS" if (
        sage["model_DER"] == 1.0
        and sage["model_BBR"] == 0.0
        and sage["denied_zero_side_effect"]
        and context["physical_DER"] < sage["physical_DER"]
    ) else "FAIL"
    source_files = sorted(Path(__file__).resolve().parent.glob("*.py"))
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "status": status,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "network_scope": "127.0.0.1 loopback only",
        "storage": ["SQLite", "JSON files"],
        "source_sha256": {
            str(path.relative_to(PROJECT_ROOT)): sha256(path) for path in source_files
        },
    }
    payload = {"manifest": manifest, **result}
    (output / "results.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output / "report.md").write_text(
        markdown_report(result, manifest), encoding="utf-8"
    )
    (output / "table_integration.tex").write_text(
        latex_table(result), encoding="utf-8"
    )
    write_csv(output / "decisions.csv", result["decision_records"])
    print(json.dumps({"output": str(output), **manifest, "summary": {
        "context": context,
        "sage": sage,
        "model_fidelity": result["model_fidelity"],
    }}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
