import json
import unittest
from unittest.mock import patch

from .dataset import load_implicit_cases
from .implicit_run import evaluate, messages_for


class ImplicitBoundaryTests(unittest.TestCase):
    def test_all_cases_are_explicit_boundary_oracles(self):
        cases = load_implicit_cases()
        self.assertEqual(len(cases), 12)
        self.assertTrue(all(case["business_expected"] == "DENY" for case in cases))
        self.assertTrue(all(case["sage_assessment"] == "UNSUPPORTED_PROPERTY" for case in cases))

    def test_model_input_does_not_expose_backend_semantics(self):
        for case in load_implicit_cases():
            text = json.dumps(messages_for(case), ensure_ascii=False)
            self.assertNotIn("reads", text)
            self.assertNotIn("writes", text)
            self.assertNotIn("gen", text)
            self.assertNotIn("UNSUPPORTED_PROPERTY", text)

    def test_valid_deny_and_allow(self):
        case = load_implicit_cases()[0]
        deny = {"decision": "DENY", "risk_type": "branch", "reason": "observable choice"}
        allow = {"decision": "ALLOW", "risk_type": "none", "reason": "no disclosure"}
        self.assertTrue(evaluate(case, {"transport_status": "OK", "finish_reason": "stop", "raw_content": json.dumps(deny)})["correct"])
        self.assertFalse(evaluate(case, {"transport_status": "OK", "finish_reason": "stop", "raw_content": json.dumps(allow)})["correct"])


if __name__ == "__main__":
    unittest.main()
