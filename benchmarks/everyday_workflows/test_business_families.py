import unittest

from sage.v2.scenario import build_scenario
from sage.v2.synthesis import direct_sage

from .business_families import BUILDERS, assess, build_family


class BusinessFamilyTests(unittest.TestCase):
    def test_metadata_and_public_boundary(self):
        seen_ids = set()
        target_tools = set()
        for name in BUILDERS:
            case = build_family(name, 64)
            self.assertEqual(case["dataset_role"], "derived-development")
            self.assertEqual(case["dispatch_count"], 64)
            self.assertNotIn(case["id"], seen_ids)
            seen_ids.add(case["id"])
            target_tools.add(case["target_tool"])
            for tool in case["public"]["tools"]:
                self.assertEqual(set(tool), {"agent", "tool", "params", "description"})
        self.assertEqual(len(target_tools), len(BUILDERS))

    def test_direct_sage_is_exact_on_diagnostics(self):
        for name in BUILDERS:
            with self.subTest(family=name):
                case = build_family(name, 64)
                scenario = build_scenario(case["spec"])
                result = assess(case, direct_sage(scenario.model, scenario.policy))
                self.assertEqual(result["coverage_certificate"], "SUFFICIENT_SAFE")
                self.assertEqual((result["missed"], result["blocked"]), (0, 0))
                self.assertEqual(result["prefix_block_decisions"], 0)
                self.assertGreater(result["dangerous_probes"], 0)
                self.assertGreater(result["benign_probes"], 0)

    def test_counts_are_nested_and_deterministic(self):
        for name in BUILDERS:
            with self.subTest(family=name):
                smaller = build_family(name, 56)
                larger = build_family(name, 72)
                self.assertEqual(smaller, build_family(name, 56))
                self.assertEqual(larger["actions"][:len(smaller["actions"])], smaller["actions"])
                self.assertEqual(larger["dispatch_count"], 72)

    def test_unknown_family_is_rejected(self):
        with self.assertRaises(ValueError):
            build_family("unknown", 64)


if __name__ == "__main__":
    unittest.main()
