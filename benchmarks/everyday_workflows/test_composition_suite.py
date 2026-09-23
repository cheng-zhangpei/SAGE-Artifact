import unittest

from .composition_suite import COUNTS, FAMILIES, build_suite, validate_case


class CompositionSuiteTests(unittest.TestCase):
    def test_shape_and_nested_actions(self):
        cases = build_suite()
        self.assertEqual(len(cases), 36)
        self.assertEqual(len({case["id"] for case in cases}), 36)
        self.assertEqual(len(FAMILIES), 6)
        for family in FAMILIES:
            group = [case for case in cases if case["family"] == family]
            self.assertEqual([case["dispatch_count"] for case in group], list(COUNTS))
            previous = []
            for case in group:
                self.assertEqual(case["actions"][:len(previous)], previous)
                previous = case["actions"]

    def test_direct_sage_oracles(self):
        for case in build_suite():
            result = validate_case(case)
            self.assertEqual((result["missed"], result["blocked"]), (0, 0))


if __name__ == "__main__":
    unittest.main()
