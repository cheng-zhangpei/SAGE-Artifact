# Matched cross-runtime audit: AgentSpec and FIDES

Both systems use the same 72 tasks, public semantic payloads, MiMo-v2.5, temperature 0.2, 16,384-token ceiling, target-probe oracles, deterministic terminal-brace normalization, and SAGE-first additive composition.

| Runtime | Arm | Loaded | Invalid | Runtime-error tasks | DER | BBR | Unknown probes |
|---|---|---:|---:|---:|---:|---:|---:|
| AgentSpec | candidate | 72/72 | 0 | 5 | 61.63% | 30.79% | 1608 |
| AgentSpec | candidate_plus_sage | 72/72 | 0 | 5 | 100.00% | 30.79% | 830 |
| FIDES | candidate | 68/72 | 4 | 8 | 55.41% | 30.27% | 2328 |
| FIDES | candidate_plus_sage | 68/72 | 4 | 8 | 100.00% | 30.27% | 1379 |
| DirectSAGE | direct_sage | 72/72 | 0 | 0 | 100.00% | 0.00% | 0 |

DER/BBR exclude unknown probes in both runtimes. Invalid and runtime-error outcomes remain visible and are not treated as denials. The systems receive the same trusted event labels and concrete parameters.

The native authoring interfaces remain intentionally different: AgentSpec uses a deterministic memoryless custom predicate executed by its upstream RuleInterpreter, whereas FIDES uses the public full-trace Python policy convention reproduced from its tutorial. Therefore compare the within-runtime change after adding SAGE; do not rank raw candidate quality across runtimes.

AgentSpec is exercised through its frozen upstream interpreter. The public FIDES repository does not expose the paper's complete AgentDojo runtime, so the FIDES arm is an interface-level reproduction on the shared benchmark.
