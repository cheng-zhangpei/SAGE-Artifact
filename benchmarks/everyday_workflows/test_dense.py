import unittest

from sage.v2.guards import Constraint, ParamFilter
from sage.v2.scenario import build_scenario
from sage.v2.synthesis import direct_sage

from .dense import DENSE_LADDER, assess, build, build_count, build_ladder


class DenseTests(unittest.TestCase):
    def test_smooth_ladder(self):
        self.assertEqual(DENSE_LADDER, tuple(range(16, 97, 8)))
        previous = []
        for step, count in enumerate(DENSE_LADDER, 1):
            case = build_ladder(step)
            self.assertEqual(case["dispatch_count"], count)
            self.assertEqual(case["actions"][:len(previous)], previous)
            previous = case["actions"]
        for step in (0, len(DENSE_LADDER) + 1, True):
            with self.assertRaises(ValueError):
                build_ladder(step)

    def test_intermediate_counts(self):
        previous = build(2)["actions"]
        for count in (64, 80, 96):
            case = build_count(count)
            self.assertEqual(case["actions"][:len(previous)], previous)
            self.assertEqual(case["dispatch_count"], count)
            scenario = build_scenario(case["spec"])
            result = assess(case, direct_sage(scenario.model, scenario.policy))
            self.assertEqual((result["missed"], result["blocked"]), (0, 0))
            previous = case["actions"]
        for count in (0, 163, True):
            with self.assertRaises(ValueError):
                build_count(count)

    def test_levels_and_baselines(self):
        previous = set()
        for level, count in ((1, 16), (2, 48), (3, 96)):
            case = build(level)
            self.assertEqual(case["dispatch_count"], count)
            signatures = {str(entry["params"]) + entry["agent"] for entry in case["actions"]}
            self.assertTrue(previous <= signatures)
            previous = signatures
            scenario = build_scenario(case["spec"])
            result = assess(case, direct_sage(scenario.model, scenario.policy))
            self.assertEqual(result["coverage_certificate"], "SUFFICIENT_SAFE")
            self.assertEqual(result["missed"], 0)
            self.assertEqual(result["blocked"], 0)
            self.assertGreater(result["dangerous_probes"], 0)
            self.assertGreater(result["benign_probes"], 0)
            for tool in case["public"]["tools"]:
                self.assertEqual(set(tool), {"agent", "tool", "params", "description"})

    def test_empty_guards_miss_danger(self):
        result = assess(build(1), ())
        self.assertGreater(result["missed"], 0)
        self.assertEqual(result["coverage_certificate"], "INCONCLUSIVE")

    def test_overbroad_guards_block_benign(self):
        case = build(1)
        guards = [Constraint(agent=agent, tool="dispatch", param_filter=ParamFilter(match_all=True),
                             forbidden_labels=frozenset(case["labels"])) for agent in ("support", "finance")]
        result = assess(case, guards)
        self.assertEqual(result["missed"], 0)
        self.assertGreater(result["blocked"], 0)


if __name__ == "__main__":
    unittest.main()
