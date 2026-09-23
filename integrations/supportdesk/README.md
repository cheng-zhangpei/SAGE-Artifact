# Local support-desk integration

This integration is an end-to-end, loopback-only system for evaluating SAGE at
a real tool-call boundary. It uses:

- SQLite for agent contexts, tickets, internal messages, and deployments;
- JSON files for shared logs and configuration sources;
- an actual HTTP server bound to `127.0.0.1` for external-send effects;
- a context-only baseline and a deployed DirectSAGE reference monitor;
- 16 predeclared workflows spanning confidentiality, integrity, generated
  labels, target parameters, multi-write atomicity, and model fidelity.

No dangerous payload leaves the host. The external receiver is a loopback
capture server created by the experiment itself.

Run the integration:

```powershell
.\.venv\Scripts\python.exe -m integrations.supportdesk.run_experiment
```

Run its tests:

```powershell
.\.venv\Scripts\python.exe -m pytest integrations\supportdesk\tests -q
```

Every experiment creates a new timestamped directory below
`experiments/reports/runs/` with raw decisions, CSV output, a manifest, and a
Markdown report. Denied calls are checked against full before/after snapshots so
partial file, database, or network side effects fail the run.

`W15_sanitized_pii_summary` is intentionally included as a negative fidelity
case. The real tool removes the email and is physically safe, but the current
union-flow semantics conservatively propagates every read label. Reporting this
over-blocking case keeps the integration claim honest and identifies a concrete
method extension for trusted declassification.
