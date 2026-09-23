# Public workflow study protocol, pilot revision 2026-09-08

## Frozen-study reproduction

After collection and structural inventory, reproduce the frozen review, SAGE
checks, fixed-seed audit sample, reports, and CSV tables with:

`python experiments/workflow_survey/run_frozen_study.py --root experiments/reports/workflow_survey_20260908`

The source-review decisions are explicit in `build_candidate_manifest.py`.
Changing one requires regenerating the manifest and all dependent tables.

## Objective and scope

Assess where public, independently authored LLM workflows expose resources through incomplete monitoring interfaces, and whether SAGE can diagnose observation collisions under reviewed contracts. The unit is a published workflow, not a framework. This is a pilot protocol written after exploratory examination of several examples; it is NOT a preregistration or blinded study.

The intended external corpus was the 6,003 n8n workflows in Tang et al., arXiv:2606.29116v2. The paper's TeX availability statement promises an archival release upon acceptance. Its Google Sites page links a Google Drive file, but anonymous retrieval requires sign-in. No original corpus has been obtained. The independent public API snapshot MUST NOT be described as the authors' 6,003 corpus.

## Collection

Use the public n8n template catalog, with rows=1000 and skip offsets. Record raw index pages, the first reported total, duplicate IDs, unique count, collection timestamps, and per-workflow SHA256 hashes. The catalog can change while paging; report this uncertainty. Download only free publicly retrievable templates. Do not run code from templates, contact template authors, or use embedded account configurations. Views indicate page exposure, not deployments or users.

## Stage A: automated structural inventory

Inventory all downloaded JSON, including negative and invalid entries. Detect known LLM/agent nodes; separate chat-model/embedding auxiliary nodes from main execution nodes. Report code nodes, cycles, invalid references, explicit file reads, binary sink parameters and cross-node references.

Candidate patterns: explicit file source followed by a binary sink, with an earlier AI step and no intervening AI step on the inspected main-graph segment. These are STRUCTURAL CANDIDATES, not collisions. Preserve all candidate node names and path evidence. Do not infer information-flow labels from titles, names, model-generated judgments or page popularity.

Custom HTTP LLM calls, dynamic expressions, disconnected subworkflows, external tools and unknown node types lower coverage. Report these rather than silently inventing contracts. Fingerprints can identify structural duplicates for review but cannot establish semantic equality. Public templates can be tutorial artifacts.

## Stage B: contract review and SAGE

Select candidate and noncandidate workflows by explicit rules, retaining original graph and node versions. Record source citations for reads/writes, treatment of AI context, parameter resolution, source labels and forbidden targets. Distinguish native behavior from study-added safety policy and fixtures.

Only reviewed models enter substantive SAGE checking. Existing observation_ctx/event/full and observation_collisions are the decision engine. On bounded trace-prefix domains, a collision witness is valid for that modeled domain but absence of collision is not an exhaustive project proof. Search limits, unsupported semantics and contract uncertainty are distinct statuses.

Compare observations with M, B, states and inputs fixed. Do not erase ctx labels to manufacture a witness. Label refinement, new source distinctions, sanitizer rules or per-field contracts are model changes and must be evaluated separately.

## Stage C: controlled replay

Replay the original data handling against local capture endpoints, without live email/social posts or real credentials. A mock remote service is a controlled integration experiment, not a production deployment. Where possible run original implementation functions and record versions/hashes. Check actual output bytes or MIME, not success strings. Hold LLM outputs fixed initially to isolate the observation intervention; later model calls are only warranted if this changes what can be learned.

Measure safety and normal-operation completion against independent fixture provenance and expected data. Separate model-domain BBR from physical completion. Any large synthetic fixture count must not be presented as independent workflow count.

## Outcomes and stop conditions

## Attribution of blocking (added 2026-09-09)

Classify each investigated event using an independent concrete allowed/forbidden judgment, the model danger predicate, observation equivalence, and the implemented decision. Missing independent judgment means `unknown`, not model error.

1. Concrete allowed, model dangerous: model-induced blocking candidate; require a soundness justification for any proposed refinement.
2. Concrete allowed and model benign, but shares an observation with a model-dangerous event: observation-induced unavoidable blocking for the stated controller class/domain.
3. Model benign and no dangerous observation mate, but deployed guard denies: guard-induced blocking candidate (relative to the chosen domain).

These categories classify a particular event under a particular model and observation. A workflow can exhibit more than one category; changes across models require reclassification. Incomplete domain exploration cannot establish that no dangerous mate exists.

The external-validity comparison fixes the reviewed model, policy, event domain, and fixtures, and changes only the observation construction. Any coarse/refined model comparison is a supplementary boundary calibration and must not be pooled with the main observation result. Label fixtures and destination policies remain study inputs unless independently provided by the source application.

Promising onboarding follow-up: the native aggregate contains both AI-authored JSON and downloaded binary documents; welcome mail attaches binaries, HR notification uses JSON only. A whole-item contract can contaminate the notification with document labels, whereas a reviewed field-level contract may avoid this. This is a hypothesis, not yet a demonstrated model-refinement result. Verify actual resolved parameters and output bytes before claiming improvement; do not infer confidentiality or declassification with an LLM.

Deliver raw corpus, reproducible inventory, supported/unsupported coverage, reviewed contracts, SAGE witnesses and any executed replay results. If no credible collision is found, report that result and why (e.g., taint already in ctx, unavailable labels, unsupported custom code, or no independent policy). Do not expand the theory or repeatedly redesign examples just to obtain a positive outcome.

The supplied paid model API is authorized for necessary semantic assistance, but cannot be used as a trusted automatic declassification oracle. Default stage A/B parser work uses no model calls. No secret values should appear in logs or artifacts.
