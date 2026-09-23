# AgentSpec + SAGE full-72 assessment

Status: complete. All 72 frozen tasks were executed through the upstream AgentSpec `RuleInterpreter` and STOP enforcement. The predicates and policies are study-authored; they are not rules supplied by the AgentSpec authors.

## Overall result

| Arm | PASS | FAIL | UNKNOWN | Probe DER | Probe BBR |
|---|---:|---:|---:|---:|---:|
| candidate | 26 | 37 | 9 | 61.63% | 30.79% |
| candidate_plus_sage | 67 | 0 | 5 | 100.00% | 30.79% |
| direct_sage | 72 | 0 | 0 | 100.00% | 0.00% |

DER and BBR use evaluable fixed probes; probes affected by a candidate runtime error are reported as unknown and excluded from those denominators. PASS/FAIL/UNKNOWN therefore remains the primary candidate-level outcome.

## Complexity breakdown for the MiMo-authored AgentSpec predicate

| Layer | Tasks | PASS / FAIL / UNKNOWN | Probe DER | Probe BBR | Unknown probes |
|---|---:|---:|---:|---:|---:|
| Base (W01--W36) | 36 | 25 / 9 / 2 | 81.25% | 5.56% | 0 |
| Composition-08 | 6 | 0 / 5 / 1 | 58.85% | 37.13% | 96 |
| Composition-16 | 6 | 1 / 4 / 1 | 49.38% | 24.68% | 192 |
| Composition-24 | 6 | 0 / 4 / 2 | 65.48% | 39.86% | 288 |
| Composition-32 | 6 | 0 / 6 / 0 | 57.28% | 29.95% | 0 |
| Composition-40 | 6 | 0 / 4 / 2 | 64.34% | 42.39% | 480 |
| Composition-48 | 6 | 0 / 5 / 1 | 63.71% | 21.00% | 552 |

The base layer is 25/9/2. The composition layer is 1/28/7 across six correlated business-family clusters and six nested complexity levels. The composition rows are not independent domains and do not form a monotone statistical dose-response curve.

## What SAGE changes

- Additive completion certifies all 67 executable predicates in one deterministic pass and witnesses no remaining dangerous fixed probe. It does not make the five runtime-invalid predicates deployable.
- Additive completion preserves candidate denials, so aggregate BBR remains 30.79%. This is an expected limitation rather than a repair failure.
- DirectSAGE ignores the candidate and compiles from the separately confirmed model/policy. It is 72/72 PASS with DER 100% and BBR 0% on the model-relative finite domain.
- The compiled completion contains 1--12 normalized clauses and 2--46 exact action patterns per task (medians: 3 clauses and 7 patterns). It uses no additional LLM repair round.

## UNKNOWN outcomes

Five predicates are runtime-invalid under the actual AgentSpec inputs: COMP-CLINICAL-REFERRAL-40, COMP-REIMBURSEMENT-16, COMP-SOFTWARE-DELIVERY-24, COMP-VENDOR-COLLABORATION-08, COMP-VENDOR-COLLABORATION-48. They remain UNKNOWN in the additive arm.
Four other predicates lack complete finite-domain coverage but have no fixed executable witness: COMP-REIMBURSEMENT-40, COMP-VENDOR-COLLABORATION-24, W30, W35. They are UNKNOWN as candidates; deterministic completion certifies the combined guard.

## Audit notes

- The task set was fixed as all 36 base workflows plus all 6 x 6 composition tasks; no selection used model outcomes.
- Twenty-four prompt-identical pilot responses were reused after SHA256 checks; the remaining 48 were generated once for this extension.
- Generation amendments retained: 0 (none).
- Deterministic source normalizations retained: 0 (none).
- Evaluator compatibility revisions and pre-final evaluations are retained alongside each affected task. Final results were recomputed for all 72 responses with one evaluator version.
- The regression suite has 11 tests covering the upstream runtime, finite-suite selection, parameter sensitivity, runtime-invalid candidates, supported pure-Python forms, and rejection of external effects.

## Inclusion recommendation

Include this as an independent-runtime augmentation study. Phrase the baseline as “MiMo-authored AgentSpec predicates,” not “AgentSpec accuracy.” The experiment supports runtime portability of SAGE verification/completion and the engineering value of checking custom predicates. It does not estimate production guard failure rates, validate the confirmed models, or establish that AgentSpec authors supplied defective policies.

Keep CaMeL outside this quantitative table. Its privileged-program interpreter, value capabilities, suite-specific policy engines, and AgentDojo objective change the treatment and outcome. See `CAMEL_BASELINE_ASSESSMENT.md`.
