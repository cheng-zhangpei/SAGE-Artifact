from __future__ import annotations
"""
benchmarks/context_invisible/runner.py  (v3 - integrated model + physical)
"""
import json, sys, yaml
from pathlib import Path
from collections import defaultdict
from sage.v2.model import Location

BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH_DIR.parents[1]))

from sage.v2.scenario import build_scenario
from sage.v2.semantics import event_taint, forbidden_targets_of_action


def load_cases():
    cases_dir = BENCH_DIR / "cases"
    cases = []
    skipped = []

    if not cases_dir.exists():
        print(f"ERROR: {cases_dir} not found")
        return []

    for case_dir in sorted(cases_dir.iterdir()):
        if not case_dir.is_dir():
            continue
        scenario_path = case_dir / "scenario.json"
        oracle_path = case_dir / "oracle.yaml"

        if not scenario_path.exists() or not oracle_path.exists():
            skipped.append((case_dir.name, "missing scenario.json or oracle.yaml"))
            continue
        if scenario_path.stat().st_size == 0:
            skipped.append((case_dir.name, "scenario.json is empty"))
            continue
        if oracle_path.stat().st_size == 0:
            skipped.append((case_dir.name, "oracle.yaml is empty"))
            continue

        try:
            spec = json.loads(scenario_path.read_text(encoding="utf-8"))
            oracle = yaml.safe_load(oracle_path.read_text(encoding="utf-8"))
            scenario = build_scenario(spec)
            cases.append({"dir": case_dir, "scenario": scenario, "oracle": oracle})
        except json.JSONDecodeError as e:
            skipped.append((case_dir.name, f"JSON parse error: {e}"))
        except yaml.YAMLError as e:
            skipped.append((case_dir.name, f"YAML parse error: {e}"))
        except Exception as e:
            skipped.append((case_dir.name, f"build error: {e}"))

    if skipped:
        print(f"WARNING: Skipped {len(skipped)} invalid case(s):")
        for name, reason in skipped:
            print(f"  - {name}: {reason}")
        print()

    return cases


def find_target_action(scenario, oracle):
    t = oracle["target_action"]
    for a in scenario.model.actions:
        if (a.agent == t["agent"] and a.tool == t["tool"]
                and a.params == t["params"]):
            return a
    for a in scenario.model.actions:
        if (a.agent == t["agent"] and a.tool == t["tool"]
                and str(a.params) == str(t["params"])):
            return a
    raise ValueError(f"Target action not found: {t}")


def run_model_level(cases):
    """Model-level verification: event taint, SAGE decision, collision analysis."""
    print("=" * 70)
    print("  Phase 1: Model-Level Verification")
    print("=" * 70)
    print()

    results = []
    for case in cases:
        sc, oracle = case["scenario"], case["oracle"]
        action = find_target_action(sc, oracle)
        eta = event_taint(sc.initial_state, action)
        q_b = forbidden_targets_of_action(sc.policy, action)
        is_danger = bool(eta & q_b)
        sage_dec = "DENY" if is_danger else "ALLOW"

        # 统一使用 Location.ctx(action.agent) 构造 O_ctx
        ctx_loc = Location.ctx(action.agent)
        ctx_labels = frozenset(sc.initial_state.get(ctx_loc))

        results.append({
            "case_id": f"{oracle['pair_id']}_{oracle['class']}",
            "class": oracle["class"],
            "eta": sorted(eta),
            "q_b": sorted(q_b),
            "is_danger": is_danger,
            "sage": sage_dec,
            "oracle_sage": oracle["expected"]["sage_decision"],
            "o_ctx": (action.agent, action.tool, action.params_items, ctx_labels),
            "o_event": (action.agent, action.tool, action.params_items, eta),
        })

    # Table
    print(f"{'Case':<20} {'Class':<8} {'eta':<12} {'q_b':<12} "
          f"{'SAGE':<7} {'Oracle':<7} {'Match'}")
    print("-" * 80)
    all_pass = True
    for r in results:
        match = "OK" if r["sage"] == r["oracle_sage"] else "FAIL"
        if r["sage"] != r["oracle_sage"]:
            all_pass = False
        print(f"{r['case_id']:<20} {r['class']:<8} "
              f"{str(r['eta']):<12} {str(r['q_b']):<12} "
              f"{r['sage']:<7} {r['oracle_sage']:<7} {match}")

    # Context-only baseline
    print("\n--- Context-Only Baseline (Canonical) ---")
    obs_classes = defaultdict(list)
    for r in results:
        obs_classes[r["o_ctx"]].append(r)

    ctx_decisions = {}
    for obs, members in obs_classes.items():
        has_danger = any(m["is_danger"] for m in members)
        verdict = "DENY" if has_danger else "ALLOW"
        for m in members:
            ctx_decisions[m["case_id"]] = verdict

    print(f"{'Case':<20} {'CtxOnly':<10} {'SAGE':<7} {'Difference'}")
    print("-" * 60)
    for r in results:
        ctx = ctx_decisions[r["case_id"]]
        diff = "SAME" if ctx == r["sage"] else "DIFFERS"
        print(f"{r['case_id']:<20} {ctx:<10} {r['sage']:<7} {diff}")

    # Collision analysis
    print("\n--- Collision Analysis ---")
    pairs = defaultdict(list)
    for r in results:
        pair_id = r["case_id"].rsplit("_", 1)[0]
        pairs[pair_id].append(r)

    for pair_id, members in sorted(pairs.items()):
        dangers = [m for m in members if m["is_danger"]]
        benigs = [m for m in members if not m["is_danger"]]
        if not dangers or not benigs:
            continue
        ctx_collide = bool({m["o_ctx"] for m in dangers} & {m["o_ctx"] for m in benigs})
        evt_collide = bool({m["o_event"] for m in dangers} & {m["o_event"] for m in benigs})
        print(f"  Pair {pair_id}: O_ctx collision={ctx_collide}, O_event collision={evt_collide}")

    # Metrics
    print("\n--- Metrics ---")
    n_d = sum(1 for r in results if r["is_danger"])
    n_b = sum(1 for r in results if not r["is_danger"])
    sage_der = sum(1 for r in results if r["is_danger"] and r["sage"] == "DENY") / max(n_d, 1)
    sage_bbr = sum(1 for r in results if not r["is_danger"] and r["sage"] == "DENY") / max(n_b, 1)
    ctx_der = sum(1 for r in results if r["is_danger"] and ctx_decisions[r["case_id"]] == "DENY") / max(n_d, 1)
    ctx_bbr = sum(1 for r in results if not r["is_danger"] and ctx_decisions[r["case_id"]] == "DENY") / max(n_b, 1)

    print(f"  Danger: {n_d}, Benign: {n_b}")
    print(f"  {'Monitor':<15} {'DER':<10} {'BBR':<10}")
    print(f"  {'SAGE':<15} {sage_der:.0%}{'':<6} {sage_bbr:.0%}")
    print(f"  {'Context-only':<15} {ctx_der:.0%}{'':<6} {ctx_bbr:.0%}")

    print(f"\n{'MODEL-LEVEL ALL PASS' if all_pass else 'MODEL-LEVEL SOME FAILED'}")
    return all_pass


def run_physical_level(cases):
    """Physical verification: real SQLite + HTTP, snapshot comparison."""
    import sys
    sys.path.insert(0, str(BENCH_DIR))  # 添加当前目录到搜索路径
    from backends import BackendPool
    # Filter cases that have infrastructure.json
    physical_cases = [c for c in cases if (c["dir"] / "infrastructure.json").exists()]

    if not physical_cases:
        print("\n  (No infrastructure.json found, skipping physical verification)")
        return True

    print()
    print("=" * 70)
    print("  Phase 2: Physical-Level Verification")
    print("=" * 70)
    print()

    results = []
    for case in physical_cases:
        sc, oracle = case["scenario"], case["oracle"]
        infra = json.loads(
            (case["dir"] / "infrastructure.json").read_text(encoding="utf-8")
        )

        action = find_target_action(sc, oracle)
        eta = event_taint(sc.initial_state, action)
        q_b = forbidden_targets_of_action(sc.policy, action)
        is_danger = bool(eta & q_b)
        sage_dec = "DENY" if is_danger else "ALLOW"

        # Setup physical backends
        pool = BackendPool(infra)
        pool.setup()
        snap_before = pool.snapshot()

        # Execute or deny
        if sage_dec == "ALLOW":
            steps = infra.get("physical_effect", {}).get("steps", [])
            pool.execute_effect(steps)

        snap_after = pool.snapshot()

        # Verify
        checks = {}
        if sage_dec == "DENY":
            checks["correct_decision"] = (sage_dec == oracle["expected"]["sage_decision"])
            checks["sqlite_unchanged"] = (snap_before.get("sqlite") == snap_after.get("sqlite"))
            checks["http_no_requests"] = (len(snap_after.get("http_requests", [])) == 0)
        else:
            checks["correct_decision"] = (sage_dec == oracle["expected"]["sage_decision"])
            expected_count = infra.get("expected", {}).get("if_allowed", {}).get("http_request_count", 0)
            actual_count = len(snap_after.get("http_requests", []))
            checks["http_request_count"] = (actual_count == expected_count)

        pool.teardown()

        results.append({
            "case_id": f"{oracle['pair_id']}_{oracle['class']}",
            "class": oracle["class"],
            "sage": sage_dec,
            "oracle": oracle["expected"]["sage_decision"],
            "checks": checks,
            "all_pass": all(checks.values()),
        })

    # Report
    print(f"{'Case':<18} {'Class':<8} {'SAGE':<7} {'Oracle':<7} {'Checks'}")
    print("-" * 75)
    all_ok = True
    for r in results:
        mark = "OK" if r["all_pass"] else "FAIL"
        detail = ", ".join(f"{k}={'OK' if v else 'FAIL'}" for k, v in r["checks"].items())
        print(f"{r['case_id']:<18} {r['class']:<8} {r['sage']:<7} "
              f"{r['oracle']:<7} {mark} {detail}")
        if not r["all_pass"]:
            all_ok = False

    print(f"\n{'PHYSICAL-LEVEL ALL PASS' if all_ok else 'PHYSICAL-LEVEL SOME FAILED'}")
    return all_ok


def run_all():
    cases = load_cases()
    if not cases:
        print("ERROR: No valid cases found")
        return False

    print(f"Loaded {len(cases)} cases\n")

    model_ok = run_model_level(cases)
    physical_ok = run_physical_level(cases)

    print()
    print("=" * 70)
    if model_ok and physical_ok:
        print("  ALL PHASES PASS")
    else:
        print("  SOME PHASES FAILED")
    print("=" * 70)

    return model_ok and physical_ok


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)
