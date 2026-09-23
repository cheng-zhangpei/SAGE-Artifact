# SAGE Context-Invisible IFC Benchmark — Final Experiment Report

> **Date**: 2026-08-17
> **Environment**: Python 3.10, Ubuntu 22.04 (WSL)
> **Repository**: run from the root of this artifact  
> **Command**: `python3 -m benchmarks`

---

## 1. Benchmark Design

### 1.1 Overview

The Context-Invisible IFC Benchmark is a **constructed diagnostic suite** designed to empirically instantiate the theoretical predictions of SAGE's union-flow information flow control model. It is not a statistical sample of production workloads; rather, each case is a precision probe targeting a specific structural property of event-taint observation.

| Metric               | Value                             |
| -------------------- | --------------------------------- |
| Total cases          | 72                                |
| Total mirror pairs   | 36                                |
| Danger cases         | 36                                |
| Benign control cases | 36                                |
| Categories           | 5 (A / B / C / D / E)             |
| Labels exercised     | PII, CREDENTIAL, UNVERIFIED, PHI  |
| Backend types        | SQLite, Filesystem, loopback HTTP |
| Verification phases  | 2 (Model-level + Physical-level)  |

### 1.2 Category Structure

| Category | Name                          | Pairs | Cases | Core Theoretical Target                                      |
| -------- | ----------------------------- | :---: | :---: | ------------------------------------------------------------ |
| **A**    | Same-invocation hidden reads  |   8   |  16   | Necessity of $\eta_u(x)$: hidden reads invisible to $O_{\text{ctx}}$ |
| **B**    | Cross-agent accumulated taint |   8   |  16   | Union-flow propagation across agents via shared state        |
| **C**    | Parameter-dependent sinks     |   6   |  12   | Parameter-resolved $Q_B(u)$ precision (Theorem 5)            |
| **D**    | Multi-write & Gen propagation |   7   |  14   | Multi-target $Q_B$ union semantics + $\text{Gen}(u)$ contribution |
| **E**    | Composite scenarios           |   7   |  14   | Multi-dimensional composition (3–4 agents, multi-label, multi-source) |

### 1.3 Mirror Pair Invariant

Each pair consists of a **danger** case and a **benign** case that share:
- Identical caller agent, tool, resolved parameters, and caller context
- Identical write target and policy
- **Exactly one controlled difference**: the taint state of a shared resource (or the parameter determining the write target in Category C)

This design isolates the causal variable and enables direct attribution of behavioral differences to the observation space ($O_{\text{ctx}}$ vs $O_{\text{event}}$).

### 1.4 Baselines

1. **SAGE (DirectSAGE)**: Event-taint guard compiled from confirmed model. Decision: $\text{Deny}^*_B(x,u) \iff \eta_u(x) \cap Q_B(u) \neq \emptyset$.

2. **Canonical Context-Only Controller**: The information-theoretically optimal safe controller under $O_{\text{ctx}} = (a, t, p, x(\text{ctx}(a)))$. For each $O_{\text{ctx}}$ equivalence class, if any event in the class is dangerous, the entire class is denied. This is not a weak heuristic—it is the strongest possible safe policy under context-only observation.

---

## 2. Phase 1: Model-Level Verification

### 2.1 Decision Accuracy

All 72 cases match the frozen oracle: **72/72 (100%)**.

- 36 danger cases: all correctly **DENY**
- 36 benign cases: all correctly **ALLOW**

### 2.2 Core Metrics

| Monitor                  |   DER    |   BBR   |
| ------------------------ | :------: | :-----: |
| **SAGE**                 | **100%** | **0%**  |
| Context-only (canonical) |   100%   | **67%** |

- **DER** (Dangerous Event Rejection rate): Both monitors detect all 36 dangerous events.
- **BBR** (Benign Blocking Rate): SAGE blocks **zero** benign events. The canonical context-only controller blocks **24 out of 36** benign events (67%), because it cannot distinguish danger from benign within the same $O_{\text{ctx}}$ equivalence class.

### 2.3 Collision Analysis

| Category            | Pairs with $O_{\text{ctx}}$ collision | Pairs with $O_{\text{event}}$ collision |
| ------------------- | :-----------------------------------: | :-------------------------------------: |
| A (Hidden reads)    |                  7/8                  |                   0/8                   |
| B (Cross-agent)     |                  6/8                  |                   0/8                   |
| C (Param sinks)     |                  0/6                  |                   0/6                   |
| D (Multi-write/Gen) |                  5/7                  |                   0/7                   |
| E (Composite)       |                  6/7                  |                   0/7                   |
| **Total**           |               **24/36**               |                **0/36**                 |

**Key findings:**

1. **$O_{\text{ctx}}$ collision = 24/36 pairs.** In these pairs, the danger and benign cases produce identical context observations. The canonical context-only controller is mathematically forced to deny both, resulting in BBR > 0.

2. **$O_{\text{event}}$ collision = 0/36 pairs.** Event-taint observation $\eta_u(x)$ distinguishes all danger/benign pairs. SAGE achieves BBR = 0% without sacrificing DER.

3. **Category C has 0 $O_{\text{ctx}}$ collisions** by design: the danger and benign cases differ in resolved parameters, which are included in $O_{\text{ctx}}$. Category C validates a complementary property—parameter-level $Q_B(u)$ resolution—rather than collision elimination.

4. **Pairs A08, B07, B08, D04, D05, E06 have $O_{\text{ctx}}$ collision = False.** These pairs involve parameter-differentiated targets or Gen-only scenarios where $O_{\text{ctx}}$ already distinguishes the branches. They validate Gen$(u)$ contribution and parameter-resolved $Q_B$ rather than collision elimination.

### 2.4 Context-Only Baseline: Differs on 24 Benign Cases

The 24 DIFFERS cases correspond exactly to the 24 $O_{\text{ctx}}$ collision pairs. In each case:
- Context-only denies (forced by collision)
- SAGE allows (correctly distinguishes via $\eta_u(x)$)

No DIFFERS occur on danger cases: both monitors correctly deny all 36 dangerous events.

---

## 3. Phase 2: Physical-Level Verification

### 3.1 Design

Physical verification executes real backend operations:
- **SQLite** (`:memory:`): Real table creation, data insertion, and query execution
- **Filesystem**: Real file creation and reading via `tempfile.mkdtemp`
- **HTTP**: Real loopback HTTP server (ephemeral port), capturing POST requests

For each case:
1. Backend is initialized with the declared state (e.g., SQLite table populated with PII data)
2. `snapshot_before` is captured
3. SAGE decision is computed
4. If **ALLOW**: physical effect steps are executed (query DB → POST to HTTP endpoint)
5. If **DENY**: no physical effect is executed
6. `snapshot_after` is captured
7. Verification checks are applied

### 3.2 Results

**72/72 cases PASS physical verification.**

| Check                         | Danger cases (36) | Benign cases (36) |
| ----------------------------- | :---------------: | :---------------: |
| `correct_decision`            |      36/36 ✓      |      36/36 ✓      |
| `sqlite_unchanged` (DENY)     |      36/36 ✓      |         —         |
| `http_no_requests` (DENY)     |      36/36 ✓      |         —         |
| `filesystem_unchanged` (DENY) |      36/36 ✓      |         —         |
| `http_request_count` (ALLOW)  |         —         |      36/36 ✓      |

**Interpretation:**
- All 36 DENY decisions physically prevented data exfiltration: no SQL query results left the process, no HTTP requests were sent, no files were modified.
- All 36 ALLOW decisions correctly permitted legitimate operations: HTTP receivers recorded the expected number of requests.

This provides end-to-end evidence that SAGE's pre-commit mediation blocks all modeled forbidden flows **before** physical side effects are committed.

---

## 4. Per-Category Analysis

### 4.1 Category A: Same-Invocation Hidden Reads (8 pairs)

Validates that tool-internal reads of shared resources produce event-taint invisible to caller context.

| Pair | Label                 | Middleware             | $O_{\text{ctx}}$ Collision |
| ---- | --------------------- | ---------------------- | :------------------------: |
| A01  | PII                   | SQLite + HTTP          |             ✓              |
| A02  | PII                   | SQLite + HTTP          |             ✓              |
| A03  | PII                   | File + HTTP            |             ✓              |
| A04  | PII                   | File + HTTP            |             ✓              |
| A05  | PII                   | SQLite + File + HTTP   |             ✓              |
| A06  | CREDENTIAL            | SQLite + File + HTTP   |             ✓              |
| A07  | PII + CREDENTIAL      | 2×SQLite + File + HTTP |             ✓              |
| A08  | UNVERIFIED (Gen only) | File + HTTP            |             ✗              |

A08 is the exception: Gen$(u) = \{\text{UNVERIFIED}\}$ with no read taint, and the benign variant differs in parameter (publish=false), so $O_{\text{ctx}}$ already distinguishes the pair.

### 4.2 Category B: Cross-Agent Accumulated Taint (8 pairs)

Validates union-flow propagation across 2–3 agents via shared databases and files.

| Pair | Agents | Label      | Middleware    | $O_{\text{ctx}}$ Collision |
| ---- | :----: | ---------- | ------------- | :------------------------: |
| B01  |   2    | PII        | SQLite + HTTP |             ✓              |
| B02  |   2    | PII        | File + HTTP   |             ✓              |
| B03  |   3    | PII        | SQLite + HTTP |             ✓              |
| B04  |   3    | CREDENTIAL | File + HTTP   |             ✓              |
| B05  |   3    | PII        | SQLite + HTTP |             ✓              |
| B06  |   3    | CREDENTIAL | File + HTTP   |             ✓              |
| B07  |   2    | PII        | SQLite + HTTP |             ✗              |
| B08  |   2    | PII        | File + HTTP   |             ✗              |

B07/B08 are parameter-differentiated (destination=external vs internal), validating parameter-resolved $Q_B$ under persistent cross-agent taint.

### 4.3 Category C: Parameter-Dependent Sinks (6 pairs)

Validates DirectSAGE's parameter-level $Q_B(u)$ resolution (Theorem 5). All pairs have $O_{\text{ctx}}$ collision = False (parameters differ).

| Pair | Label            | Parameter                              | Real-world basis                   |
| ---- | ---------------- | -------------------------------------- | ---------------------------------- |
| C01  | PII              | destination: external/internal         | Enterprise DLP (Microsoft Purview) |
| C02  | CREDENTIAL       | storage_class: public/partner/internal | AWS S3 bucket policy               |
| C03  | PII              | export_region: non_eu/eu_internal      | GDPR Art. 44 cross-border transfer |
| C04  | PHI + CREDENTIAL | config.destination.type (nested)       | HIPAA Privacy Rule                 |
| C05  | UNVERIFIED       | registry: public_npm/internal          | SolarWinds supply chain            |
| C06  | PII              | audience: 3 values                     | PCI-DSS / SOX financial reporting  |

**C06 stress test**: 3 parameter instances, 2 forbidden, 1 allowed. A tool-wide deny baseline would block all 3 (BBR = 66.7%). SAGE blocks only the 2 forbidden instances (BBR = 0%).

### 4.4 Category D: Multi-Write & Gen Propagation (7 pairs)

Validates $Q_B(u) = \bigcup_{v \in Wr(u)} B(v)$ union semantics and Gen$(u)$ contribution to $\eta_u(x)$.

| Pair | Core verification                                            | $O_{\text{ctx}}$ Collision |
| ---- | ------------------------------------------------------------ | :------------------------: |
| D01  | Multi-write: 1 forbidden + 1 clean target                    |             ✓              |
| D02  | Multi-write: different labels on different targets           |             ✓              |
| D03  | Gen-only: Gen$(u) \neq \emptyset$, all reads clean           |             ✓              |
| D04  | Gen + read combination: $\eta = \text{Gen}(u) \cup \bigcup x(v)$ |             ✗              |
| D05  | Gen + multi-write: Gen triggers dual-publish denial          |             ✗              |
| D06  | Cross-agent Gen + multi-source read                          |             ✓              |
| D07  | Multi-write partial overlap: $\eta$ has extra labels beyond $Q_B$ |             ✓              |

### 4.5 Category E: Composite Scenarios (7 pairs)

Validates composability across all theoretical dimensions. Complexity increases from E01 to E07.

| Pair | Labels                        | Agents | Complexity                          | $O_{\text{ctx}}$ Collision |
| ---- | ----------------------------- | :----: | ----------------------------------- | :------------------------: |
| E01  | PII                           |   3    | Chain + param sink                  |             ✓              |
| E02  | CREDENTIAL + UNVERIFIED       |   3    | Multi-writer + Gen + param          |             ✓              |
| E03  | PHI + PII + CREDENTIAL        |   1    | Multi-label + multi-source + param  |             ✓              |
| E04  | UNVERIFIED                    |   2    | Cross-agent Gen + multi-write       |             ✓              |
| E05  | PII                           |   4    | 4-agent chain (longest propagation) |             ✓              |
| E06  | PII + CREDENTIAL + UNVERIFIED |   3    | Full composite (all dimensions)     |             ✗              |
| E07  | PII + UNVERIFIED              |   1    | Integrity + Confidentiality mixed   |             ✓              |

---

## 5. Summary of Findings

1. **SAGE achieves perfect safety and zero over-blocking**: DER = 100%, BBR = 0% across all 72 cases spanning 5 categories, 4 label types, and 1–4 agent configurations.

2. **Event-taint observation eliminates all observation collisions**: $O_{\text{event}}$ collision = 0/36 pairs, while $O_{\text{ctx}}$ collision = 24/36 pairs. This directly instantiates Corollary 3 of the theoretical model.

3. **The canonical context-only baseline suffers 67% BBR**: This is not a weakness of the baseline implementation—it is the information-theoretic limit of context-only observation. Any safe controller under $O_{\text{ctx}}$ must deny at least 24/36 benign cases.

4. **Parameter-resolved $Q_B(u)$ prevents tool-wide over-blocking**: Category C demonstrates that DirectSAGE's grouping by $(agent, tool, Q_B(u))$ correctly separates parameter instances with distinct target policies, avoiding the 66.7% BBR that a tool-wide deny would cause.

5. **Physical verification confirms pre-commit enforcement**: All 36 DENY decisions physically prevented data exfiltration (zero HTTP requests, zero SQLite mutations, zero filesystem changes). All 36 ALLOW decisions correctly permitted legitimate operations.

---

## 6. Threats to Validity

1. **Researcher-constructed benchmark**: All 72 cases are author-designed diagnostic probes, not sampled from production workloads. Results demonstrate structural properties of event-taint observation, not population-level statistics.

2. **Model-level taint assignment**: Taint labels in `initial_state` are declared by the benchmark designer, not automatically inferred from data content. This mirrors the confirmed-model assumption of SAGE (human-reviewed `Rd/Wr/Gen` contracts).

3. **Physical verification scope**: The physical layer verifies side-effect prevention (SQLite/File/HTTP) but does not exercise the full gRPC → SAGE Runtime → Reference Monitor call chain. End-to-end runtime integration is covered separately by the SupportDesk and Threshold experiments.

4. **Single-policy evaluation**: All cases use a single forbidden-flow policy $B$. Multi-policy or dynamically updated policies are not evaluated.

---

## 7. Reproduction

```bash
cd /path/to/SAGE-Artifact
python3 -m benchmarks
```

Expected output: `✓✓ ALL PHASES PASS` with 72/72 model-level and 72/72 physical-level verification.

**Dependencies**: Python 3.10+, `pyyaml`, `z3-solver` (for v2 core), standard library (`sqlite3`, `http.server`, `tempfile`).

---

## 8. Artifact Structure

```text
benchmarks/context_invisible/
├── __init__.py
├── runner.py              # Unified runner (model + physical)
├── backends.py            # Resource pool (SQLite, File, HTTP)
├── baselines.py           # Canonical context-only controller
└── cases/
    ├── A01_danger/
    │   ├── scenario.json
    │   ├── oracle.yaml
    │   └── infrastructure.json
    ├── A01_benign/
    │   ├── scenario.json
    │   ├── oracle.yaml
    │   └── infrastructure.json
    ├── ...
    └── E07_benign/
        ├── scenario.json
        ├── oracle.yaml
        └── infrastructure.json
```

Total: 72 case directories × 3 files = **216 core files**.

---

*Report generated from a single clean run. All results are deterministic (no LLM, no randomness).*
