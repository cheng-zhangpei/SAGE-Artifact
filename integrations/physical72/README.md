# Physical72

This package is a controlled cross-domain physical-side-effect suite. It
contains 72 workflow instances: 24 each for customer support, reimbursement
operations, and software delivery. Every scenario has 12 physically dangerous
and 12 physically benign workflows.

The suite executes real SQLite writes, filesystem writes, and HTTP POSTs to a
loopback-only receiver. It checks before/after snapshots for every decision.
It is not evidence of 72 independently observed production deployments. The
three domains repeat a common set of information-flow mechanisms with
domain-specific agents, tools, labels, destinations, and stored resources.

Run from the repository root:

```powershell
python -B -m integrations.physical72.experiment --output-dir experiments/reports/runs/physical72_RUN_ID
```

The output directory contains a manifest, every workflow/monitor record, and a
Markdown report. `SUP12B`, `REIMB12B`, and `SOFT12B` deliberately model trusted
sanitizers that are physically safe but rejected by conservative union-flow
semantics.

## Audited revision (2026-09-19)

Use `experiments/reports/runs/physical72_audited_20260919` for paper evidence.
The earlier frozen run is superseded for physical-read claims. This revision
reads actual persisted bodies/labels, checks exact outputs and unchanged inputs,
and physically executes all six comparators. Two-source cases use SQLite plus
JSON. Caller-role variants do not simulate a complete upstream agent handoff.
Run `python -m unittest integrations.physical72.test_experiment -v` for regression
and persisted-backend mutation checks. See the audited run's AUDIT.md.
