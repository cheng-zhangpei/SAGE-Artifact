# Physical72 evidence correction

Use this audited run for the manuscript; the earlier `physical72_frozen_20260919` run is superseded for physical-read claims.

The previous harness initialized backing stores but executed from in-memory fixture content. It also checked only whether any effect occurred. The revised harness reads labels and bodies from SQLite / JSON, snapshots input and output stores, checks exact receiver and stored outputs, and physically executes all six comparators. Mutation tests cover both input backends. All three unittest tests passed. The new run contains 432 executions, with snapshots in results.json.

Shared templates across three business domains are controlled instantiations, not 72 independent applications. Caller-role variation is not an executed agent-to-agent handoff. Synthetic labels and fixture policies do not establish real-world observation collisions. The main paper explicitly preserves these limits.

SAGE: 36/36 dangerous denied; 33/36 benign completed; three sanitizer abstractions cause false positives. All 39 denied SAGE calls leave observed stores and receiver unchanged. 33 allowed calls yield 39 effects (30 HTTP, six SQLite, three deployment files). These counts match the earlier aggregate rates, but the revised execution path now supports persisted-read and exact-effect claims.

Repair accounting is derived from the frozen authoring outputs and the deterministic completion protocol. It is one completion pass, not a count of iterative LLM repairs. UNKNOWN is not an authoring defect.
