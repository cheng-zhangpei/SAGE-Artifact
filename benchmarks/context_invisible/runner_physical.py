from __future__ import annotations
import json, sys, yaml
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH_DIR.parents[1]))

from sage.v2.scenario import build_scenario
from sage.v2.semantics import event_taint, forbidden_targets_of_action
from backends import BackendPool


def run_case(case_dir: Path) -> dict:
    spec = json.loads((case_dir / "scenario.json").read_text(encoding="utf-8"))
    oracle = yaml.safe_load((case_dir / "oracle.yaml").read_text(encoding="utf-8"))
    infra = json.loads(
        (case_dir / "infrastructure.json").read_text(encoding="utf-8")
    )

    scenario = build_scenario(spec)

    # 找 target action
    t = oracle["target_action"]
    action = None
    for a in scenario.model.actions:
        if (a.agent == t["agent"] and a.tool == t["tool"]
                and a.params == t["params"]):
            action = a
            break
    if action is None:
        raise ValueError(f"Target action not found: {t}")

    # SAGE 决策
    eta = event_taint(scenario.initial_state, action)
    q_b = forbidden_targets_of_action(scenario.policy, action)
    is_danger = bool(eta & q_b)
    sage_dec = "DENY" if is_danger else "ALLOW"

    # 启动真实后端
    pool = BackendPool(infra)
    pool.setup()
    snap_before = pool.snapshot()

    # 执行或拒绝
    if sage_dec == "ALLOW":
        steps = infra.get("physical_effect", {}).get("steps", [])
        pool.execute_effect(steps)

    snap_after = pool.snapshot()

    # 验证
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

    return {
        "case_id": f"{oracle['pair_id']}_{oracle['class']}",
        "class": oracle["class"],
        "sage": sage_dec,
        "oracle": oracle["expected"]["sage_decision"],
        "eta": sorted(eta),
        "checks": checks,
        "all_pass": all(checks.values()),
    }


def run_all():
    cases_dir = BENCH_DIR / "cases"
    results = []
    for case_dir in sorted(cases_dir.iterdir()):
        if not case_dir.is_dir():
            continue
        if not (case_dir / "infrastructure.json").exists():
            print(f"  SKIP {case_dir.name} (no infrastructure.json)")
            continue
        try:
            results.append(run_case(case_dir))
        except Exception as e:
            results.append({"case_id": case_dir.name, "error": str(e), "all_pass": False})

    print(f"\n{'Case':<18} {'Class':<8} {'SAGE':<7} {'Oracle':<7} {'Checks'}")
    print("-" * 75)
    all_ok = True
    for r in results:
        if "error" in r:
            print(f"{r['case_id']:<18} ERROR: {r['error']}")
            all_ok = False
            continue
        mark = "OK" if r["all_pass"] else "FAIL"
        detail = ", ".join(f"{k}={'OK' if v else 'FAIL'}" for k, v in r["checks"].items())
        print(f"{r['case_id']:<18} {r['class']:<8} {r['sage']:<7} "
              f"{r['oracle']:<7} {mark} {detail}")
        if not r["all_pass"]:
            all_ok = False

    print(f"\n{'ALL PHYSICAL TESTS PASS' if all_ok else 'SOME FAILED'}")
    return all_ok


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)
