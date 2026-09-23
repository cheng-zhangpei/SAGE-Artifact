# AgentSpec + SAGE: frozen paired authoring protocol

## Question

Can SAGE check and complete study-authored AgentSpec predicates while retaining
their decisions in AgentSpec's actual interpreter and STOP enforcement?
This is an integration/augmentation study of an existing published runtime,
not a claim that AgentSpec authors supplied incorrect benchmark policies.

## Corrected feasibility finding

AgentSpec commit `e6fa3902e2cfb9681f454b355691b771f70543f8` documents custom
Python predicates accepting `user_input`, `tool_input`, and `intermediate_steps`.
Its interpreter passes the action input to the function without stripping
parameters. Its README explicitly describes adding predicate names to the
grammar, regenerating the parser, and registering Python implementations.
Therefore absence of parameter comparisons in the stock grammar does not imply
absence of parameter-sensitive enforcement. Custom predicates are a documented
extension, rather than a reason by themselves to exclude a comparison.

The old working checkout contains a researcher-added `sage_policy_violation`.
This experiment exports the frozen upstream commit to its own output directory;
the existing checkout is preserved. It adds only `pilot_candidate` and
`pilot_completion` predicate names and regenerates ANTLR using Java 17. The
RuleInterpreter, rule dispatch and STOP implementation remain upstream code.

## Three different objects

1. The supplied natural-language flow policy defines the intended restriction.
2. MiMo-v2.5 writes a Python AgentSpec predicate from the public workflow and
   policy, with no confirmed `reads`/`writes`/`gen` arrays or oracle decisions.
3. SAGE uses the separately confirmed model/policy to check and complete the
   predicate. This additional modeling input is part of SAGE's cost.

Both baseline and completed guards receive identical original parameters and
trusted host-provided agent, tool and event labels. The host's event-label
resolver is an explicit integration prerequisite. No arm is given a per-event
danger verdict. Compiled predicates embed model-derived constant parameter
filters and forbidden labels, but do not call the SAGE decision function.

## Fixed workload and generation

24 tasks from the existing benchmark: every third base task starting W01
(12 tasks), and all six composition families at 8 and 48 dispatches (12 tasks).
The selection rule is fixed before this run's outputs. These are previously
studied benchmark families, not a new external holdout or 24 independent domains.
All tasks and prompts are saved before API requests. One draft per task,
temperature 0.2, output budget 8192, model ID `mimo-v2.5`, at most two requests
in flight. Successful outputs are never retried to obtain failures. Transport,
truncation, unsupported code and evaluation errors stop further submissions
and remain in the checkpoint for explicit handling.

The supported candidate fragment is deterministic, memoryless, side-effect-free
Python with parameter/label conditions and bounded collection comprehensions.
The prompt declares this fragment. General history-based, network-dependent,
stateful or LLM-evaluated AgentSpec predicates are outside the verification
claim. Unsupported code is an error, never automatically labelled unsafe.

## Execution, verification and measures

Each candidate and compiled completion are registered in the actual AgentSpec
predicate table. Rules trigger on real tool names. RuleInterpreter and STOP
execute for every distinct finite observed call; cached decisions only avoid
repeating identical pure observations. The SAGE checker enumerates the selected
finite action/label observation domain and checks coverage of dangerous events.
Complete coverage is a sufficient model-level safety certificate. A missing
cover is FAIL only if an existing diagnostic prefix admitted by the candidate
reaches a missed dangerous call; otherwise it is UNKNOWN.

Compiled predicates are checked against the model-derived rejection condition
on every action and every subset of the finite label universe. A mismatch
aborts evaluation. All candidates share these compiler checks; no result is
accepted on assumed compilation equivalence.

Report PASS/FAIL/UNKNOWN plus fixed-probe DER and BBR for:

- AgentSpec with the LLM-authored predicate;
- the same predicate plus the compiled SAGE completion;
- AgentSpec executing only the DirectSAGE predicate (reference).

Additive completion retains existing denials. It cannot improve BBR by deleting
rules. Probe prefixes are scored and retained separately from target decisions;
target DER/BBR is not an end-to-end task-utility or attack-success metric.
No physical backend or full LangChain LLM agent loop is claimed by this run.

## Evidence and checkpoints

- `outputs/feasibility_20260920`: three hand-written adapter controls, clearly
  separated from LLM results. Parameter omission repaired; overly restrictive
  candidate stays restrictive; correct candidate unchanged.
- `outputs/mimo24_20260920/manifest.json`: fixed version, selection and settings.
- Each task retains public prompt, confirmed model, original API response,
  predicate source, AgentSpec rules, complete observable truth table and probes.
- `outputs/mimo24_20260920/report.md` and `checkpoint.json`: progress/results.
- `test_study.py`: real interpreter tests on base and composition tasks,
  parameter discrimination, and rejection of effects in generated predicates.

No manuscript change is authorized by a successful pilot alone. Assess the
completed run's errors, information contract and modeling cost before deciding
whether to include it as an augmentation experiment in the paper.

## Full-72 extension decision

The 24-task pilot was selected before generation and established feasibility,
but it is not the final scale claim. The follow-up uses the already frozen
72-task authoring benchmark: all W01--W36 base tasks and all six composition
families at 8/16/24/32/40/48 dispatches. This includes every intermediate
composition level; no task is selected from the pilot outcomes. Frozen pilot
responses are reused only when task ID and prompt SHA256 match exactly. The
remaining 48 responses are generated once with the same model and temperature.

The full run starts with a 16384-token output budget because two pilot prompts
exhausted 8192 tokens on reasoning before completing the JSON contract. Raw
pilot truncations and their one-retry amendments remain in the pilot output.
The full run continues to classify executable counterexamples as FAIL and
runtime-invalid predicates as UNKNOWN. SAGE completion is not credited with
repairing an AgentSpec predicate that cannot execute.
