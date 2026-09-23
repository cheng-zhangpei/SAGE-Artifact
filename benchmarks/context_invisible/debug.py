# benchmarks/context_invisible/debug.py
import sys, json
from pathlib import Path

# 基于脚本自身位置，而不是 cwd
BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH_DIR.parents[1]))  # 指向 SAGE 根目录

from sage.v2.scenario import build_scenario
from sage.v2.semantics import event_taint, forbidden_targets_of_action

for name in ["A01_danger", "A01_benign"]:
    case_dir = BENCH_DIR / "cases" / name
    scenario_path = case_dir / "scenario.json"

    if not scenario_path.exists():
        print(f"ERROR: {scenario_path} not found")
        continue

    spec = json.loads(scenario_path.read_text(encoding="utf-8"))
    scenario = build_scenario(spec)

    print(f"\n=== {name} ===")
    print(f"  initial_state: {scenario.initial_state}")

    for action in scenario.model.actions:
        eta = event_taint(scenario.initial_state, action)
        q_b = forbidden_targets_of_action(scenario.policy, action)
        print(f"  action: {action.canonical()}")
        print(f"    reads:  {[str(l) for l in action.reads]}")
        print(f"    writes: {[str(l) for l in action.writes]}")
        print(f"    eta:    {sorted(eta)}")
        print(f"    q_b:    {sorted(q_b)}")
        print(f"    danger: {bool(eta & q_b)}")
