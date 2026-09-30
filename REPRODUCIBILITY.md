# Reproducibility guide

## Environment

The evaluated semantic core supports Python 3.9 or newer. Install the artifact
from the repository root:

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# POSIX shell: source .venv/bin/activate
python -m pip install -e ".[dev]"
```

The optional `llm` extra installs an OpenAI-compatible client. It is not needed
to inspect frozen responses or recompute the reported classifications:

```bash
python -m pip install -e ".[dev,llm]"
```

API credentials, when intentionally running a new authoring study, must be
provided through environment variables. Never write credentials into a source,
configuration, prompt, or output file.

## Semantic core and benchmark validation

```bash
python -m pytest sage/v2/tests -q
python -m benchmarks.everyday_workflows.validate
python -m benchmarks.everyday_workflows.composition_suite validate
```

The first command exercises transition semantics, guard evaluation,
counterexample search, coverage checking, and DirectSAGE. The latter two check
the benchmark identifiers, finite action spaces, safe initial states, declared
dangerous/benign probes, and compiled guards.

## Frozen guard-authoring responses and coverage audit

The original model responses and prompts are in
`artifacts/fse2027/authoring72/raw`. The `mimo` and `gpt55` report files retain
earlier bounded-search P/F/U classifications; these are historical records,
not the final P/F/U values used in the paper. The final classification applies
the conservative coverage check and replays candidate-admitted unsafe witnesses.
It leaves the fixed-probe DER and BBR counts unchanged.

Recompute this audit without contacting a model provider:

```bash
python -m benchmarks.everyday_workflows.audit_frozen_composition \
  --output output/authoring_coverage_recomputed.json
```

The recomputed JSON should match
`artifacts/fse2027/authoring72/coverage_audit_results.json`. The composition
counts are MiMo 26 PASS / 9 FAIL / 1 UNKNOWN and GPT-5.5 25 PASS / 11 FAIL /
0 UNKNOWN; adding the 36 base tasks yields the paper's 61/10/1 and 61/11/0.

## AgentSpec runtime study

The frozen study uses AgentSpec commit
`e6fa3902e2cfb9681f454b355691b771f70543f8`. Its protocol and integration
boundary are documented in
`experiments/agentspec_native_pilot/PROTOCOL.md`. Recompute the summary from the
committed task records:

```bash
python experiments/agentspec_native_pilot/summarize_results.py \
  --output artifacts/fse2027/agentspec_mimo72
```

This command writes derived summary files into the selected directory. Run it
on a copy of `agentspec_mimo72` when checking the committed file hashes.

The study registers the candidate and completed predicates in AgentSpec's
interpreter and uses AgentSpec's STOP enforcement. Rebuilding the interpreter
checkout additionally requires Git, Java 17, and network access to the upstream
repository. Clone `https://github.com/haoyuwang99/AgentSpec.git` into
`external/AgentSpec` (or set `AGENTSPEC_SOURCE` to an existing checkout). The
runner archives the pinned commit and uses `java` from `PATH`; set `JAVA` to a
Java 17 executable when needed. The paper does not treat this experiment as a comparison against
author-supplied AgentSpec policies.

## FIDES policy-interface reproduction

This arm reproduces the policy-evaluation logic published in the FIDES tutorial:
labelled `ToolCall` traces are checked before effects, and rejection raises
`PolicyViolation`. The shared benchmark supplies trusted event labels so that
the study isolates policy authoring and SAGE completion; it does not reproduce
the full FIDES planner or AgentDojo integration.

Recompute the matched probe summary and unified table from frozen responses:

```bash
python -m experiments.fides_native_pilot.matched_probe_evaluate --output artifacts/fse2027/fides_mimo72
python experiments/cross_runtime_matched_audit.py
```

The FIDES evaluator writes per-task diagnostics. Python set iteration may
change which denied destination appears first in a diagnostic string, while
probe decisions and aggregate scores remain the same. Run it on a copy when
checking committed file hashes. Two hash seeds reproduced the frozen aggregate
summary exactly.

## Physical workflows

```bash
python -m integrations.physical72.experiment --output-dir output/physical72
python -m unittest integrations.physical72.test_experiment -v
```

The suite executes SQLite, filesystem, and loopback HTTP effects and compares
before/after snapshots. The frozen audited output is under
`artifacts/fse2027/physical72`.

## Observation diagnostic

```bash
python -m benchmarks.context_invisible.runner
```

This controlled suite contains 36 dangerous/benign pairs and evaluates the
declared observation projections. It is a mechanism diagnostic rather than an
estimate of collision prevalence in deployed guards.

## Public-workflow survey

Frozen reviewed classifications, source hashes, and the download manifest are
under `artifacts/fse2027/workflow_survey`. The complete third-party download
cache is intentionally omitted. The survey supports the paper's stated
existence result under supplied policies and observations; it does not estimate
the prevalence of deployed-guard collisions.

## Frozen LLM records

The paper-facing MiMo-v2.5 and GPT-5.5 summaries and raw retained responses
for the 72 authoring tasks are under `artifacts/fse2027/authoring72`. The AgentSpec study retains its
prompts, raw responses, predicate source, compiled completion, truth tables,
and evaluations under `artifacts/fse2027/agentspec_mimo72`. Offline analysis
does not contact a model provider.

## Integrity

Run the following PowerShell snippet from the repository root to check the
frozen evidence after download:

```powershell
Get-Content artifacts/fse2027/SHA256SUMS | ForEach-Object {
  $hash, $path = $_ -split '  ', 2
  if ((Get-FileHash -Algorithm SHA256 (Join-Path artifacts/fse2027 $path)).Hash.ToLower() -ne $hash) {
    throw "Checksum mismatch: $path"
  }
}
```
