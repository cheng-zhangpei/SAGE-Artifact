"""
@function      :
@time          :2026/8/3 22:42
"""
# test_s6_bfs.py
import time
from experiments.run_llm_batch import load_scenario
from sage.v2.properties import reachable_states

scenario, _, _ = load_scenario("experiments/scenarios/s6_full")

print("Starting BFS...")
t0 = time.time()
try:
    states = reachable_states(scenario.model, scenario.initial_state, constraints=(), max_states=50000)
    print(f"BFS completed: {len(states)} states in {time.time()-t0:.2f}s")
except Exception as e:
    print(f"BFS failed after {time.time()-t0:.2f}s: {e}")
