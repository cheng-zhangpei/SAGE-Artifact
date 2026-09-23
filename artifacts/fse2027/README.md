# Frozen evaluation evidence

This directory contains the compact evidence needed to audit the manuscript's
reported counts. It deliberately excludes API credentials, virtual
environments, downloaded third-party runtimes, provider transport retries, and
the 936 MiB public-workflow download cache.

## Contents

| Directory | Frozen evidence | Main source code |
|---|---|---|
| `authoring72/mimo` | MiMo-v2.5 candidates and SAGE evaluation for 72 tasks | `benchmarks/everyday_workflows` |
| `authoring72/gpt55` | GPT-5.5 candidates and SAGE evaluation for the same 72 tasks | `benchmarks/everyday_workflows` |
| `agentspec_mimo72` | 72 MiMo predicates, compiled completions, AgentSpec rules, truth tables, and evaluations | `experiments/agentspec_native_pilot` |
| `physical72` | Audited results for 72 SQLite/filesystem/loopback-HTTP executions | `integrations/physical72` |
| `workflow_survey` | Final classification of all 38 detector-positive templates, source hashes, and download manifest | `experiments/workflow_survey` |

The controlled 36-pair observation diagnostic is versioned directly under
`benchmarks/context_invisible`, including all 72 case fixtures. The authoring
benchmark contains 36 base workflows and 36 composition tasks; the composition
levels within a business family are correlated prefixes rather than independent
domains.

## Offline checks

From the repository root, after installing `.[dev]`:

```powershell
python -m pytest sage/v2/tests benchmarks/everyday_workflows integrations/physical72 -q
python -m benchmarks.everyday_workflows.validate
python -m benchmarks.everyday_workflows.composition_suite validate
python experiments/agentspec_native_pilot/summarize_results.py --output artifacts/fse2027/agentspec_mimo72
```

The AgentSpec experiment uses upstream commit
`e6fa3902e2cfb9681f454b355691b771f70543f8`. Its protocol and extension boundary
are recorded in `experiments/agentspec_native_pilot/PROTOCOL.md`. The committed
task records retain the prompts and raw model responses, but no provider key or
request header.

The workflow survey's complete downloaded corpus is intentionally omitted.
`download_manifest.json` records the frozen inventory and source hashes;
`candidate_final_status.json` contains the complete reviewed detector-positive
population. The survey supports an existence result under study-supplied labels,
policies, and observations, rather than an estimate of deployed prevalence.

`SHA256SUMS` covers every other file in this directory and can be checked with
any SHA-256 utility.
