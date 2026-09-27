# SAGE Artifact

This repository is the anonymous replication package for **SAGE: Synthesis
and Verification of Information-Flow Guards for Tool-Using Agents under
Partial Observation**.

SAGE treats a tool-call guard as a software artifact. Given a confirmed finite
tool model and a forbidden-flow policy, it can synthesize a guard directly,
verify an executable candidate, return a counterexample for an admitted
violation, and complete missing rejection clauses. The package contains the
implementation, frozen experiment records, benchmark definitions, and the
paper's supplementary material.

## Artifact map

| Paper evidence | Reproduction code | Frozen records |
|---|---|---|
| AgentSpec runtime study on 72 authoring tasks | `experiments/agentspec_native_pilot` | `artifacts/fse2027/agentspec_mimo72` |
| FIDES policy-interface reproduction on the same tasks | `experiments/fides_native_pilot` | `artifacts/fse2027/fides_mimo72` |
| Guard authoring on the same 72 tasks | `benchmarks/everyday_workflows` | `artifacts/fse2027/authoring72` |
| Physical enforcement on 72 workflow instances | `integrations/physical72` | `artifacts/fse2027/physical72` |
| Context-invisible observation diagnostic (36 pairs) | `benchmarks/context_invisible` | Case fixtures in the same directory |
| Public-workflow survey | `experiments/workflow_survey` | `artifacts/fse2027/workflow_survey` |
| Formal semantic core and tests | `sage/v2` | Tests under `sage/v2/tests` |
| Supplementary material | -- | `supplement/SAGE_supplementary_material.pdf` |

The 72-task authoring benchmark contains 36 base workflows and 36 composition
tasks. The composition tasks are six correlated business-family ladders, not
36 independent domains. The physical suite contains 24 instances in each of
three business domains. The observation diagnostic is a controlled mechanism
suite. These scopes match the claims in the paper and supplement.

## Quick start

Requirements:

- Python 3.9 or newer;
- Java 17 and Git only for rebuilding the AgentSpec interpreter checkout;
- no API key for the offline checks below.

Create an environment and install the package:

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
```

On Windows, use `.venv\Scripts\python.exe` in place of `python` below when
needed.

Run the principal offline checks:

```bash
python -m pytest sage/v2/tests benchmarks/everyday_workflows integrations/physical72 -q
python -m benchmarks.everyday_workflows.validate
python -m benchmarks.everyday_workflows.composition_suite validate
python experiments/agentspec_native_pilot/summarize_results.py \
  --output artifacts/fse2027/agentspec_mimo72
python -m experiments.fides_native_pilot.matched_probe_evaluate --output artifacts/fse2027/fides_mimo72
python experiments/cross_runtime_matched_audit.py
```

Re-run the physical workflow experiment in a fresh output directory:

```bash
python -m integrations.physical72.experiment --output-dir output/physical72
```

Run the controlled observation diagnostic:

```bash
python -m benchmarks.context_invisible.runner
```

See [REPRODUCIBILITY.md](REPRODUCIBILITY.md) for the evidence boundary, optional
online experiments, and the location of every frozen result. The committed
model responses make the paper-facing analyses reproducible without paid API
calls.

## Integrity and anonymity

`artifacts/fse2027/SHA256SUMS` records SHA-256 digests for the frozen evidence.
API credentials are neither required for offline evaluation nor included in
this repository. Synthetic strings that resemble credentials occur only as
taint-bearing benchmark fixtures and have no external validity.

The repository is prepared for double-anonymous review. Please use the
anonymous review URL supplied in the paper rather than attempting to identify
the authors or the source repository.


