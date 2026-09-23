# Reproducibility guide

## Environment

The evaluated semantic core supports Python 3.9 or newer. Install the artifact
from the repository root:

```bash
python -m venv .venv
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

The study registers the candidate and completed predicates in AgentSpec's
interpreter and uses AgentSpec's STOP enforcement. Rebuilding the interpreter
checkout additionally requires Git, Java 17, and network access to the upstream
repository. The paper does not treat this experiment as a comparison against
author-supplied AgentSpec policies.

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

The complete paper-facing MiMo-v2.5 and GPT-5.5 records for the 72 authoring
tasks are under `artifacts/fse2027/authoring72`. The AgentSpec study retains its
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


