import json
import unittest
from unittest.mock import patch

from .dataset import load_workflows
from .evaluate import evaluate_candidate, evaluate_direct, strict_json
from .run import SYSTEM, messages_for, request_once


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflows = load_workflows()
        cls.workflow = cls.workflows[0]

    def test_all_direct_baselines(self):
        self.assertEqual(len(self.workflows), 36)
        for workflow in self.workflows:
            with self.subTest(workflow=workflow["id"]):
                result = evaluate_direct(workflow)
                self.assertEqual(result["verification_status"], "PASS")
                self.assertEqual(result["correct_pairs"], 4)
                self.assertEqual(result["probe_bbr"], 0)

    def test_empty_guards_fail(self):
        result = evaluate_candidate(self.workflow, '{"guards":[]}')
        self.assertEqual(result["verification_status"], "FAIL")
        self.assertEqual(result["probe_der"], 0)
        self.assertIsNotNone(result["counterexample"])

    def test_overblocking_is_separate_from_safety(self):
        candidate = {"guards": [
            {"agent": action["agent"], "tool": action["tool"], "params": action["params"],
             "forbidden_labels": list(self.workflow["labels"])}
            for action in self.workflow["actions"]
        ]}
        result = evaluate_candidate(self.workflow, json.dumps(candidate))
        self.assertEqual(result["verification_status"], "PASS")
        self.assertGreater(result["probe_bbr"], 0)
        self.assertGreater(result["benign_prefix_blocked"], 0)

    def test_invalid_json_and_calls(self):
        action = self.workflow["actions"][0]
        clause = {key: action[key] for key in ("agent", "tool", "params")}
        clause["forbidden_labels"] = ["NOT_DECLARED"]
        invalid = ['```json\n{"guards":[]}\n```', '{"guards":[],"guards":[]}',
                   json.dumps({"guards": [clause]})]
        clause["forbidden_labels"] = ["PII"]
        clause["params"] = {"invented": True}
        invalid.append(json.dumps({"guards": [clause]}))
        for raw in invalid:
            result = evaluate_candidate(self.workflow, raw)
            self.assertEqual(result["candidate_status"], "FORMAT_ERROR")
            self.assertEqual(result["verification_status"], "NOT_RUN")

    def test_non_json_constants(self):
        with self.assertRaises(ValueError):
            strict_json('{"value":NaN}')

    def test_unknown_is_not_pass(self):
        result = evaluate_candidate(self.workflow, '{"guards":[]}', max_states=1)
        self.assertEqual(result["verification_status"], "UNKNOWN")

    def test_prompt_has_no_backend_fields(self):
        for fragment in ("union", "Gen(", "Rd(", "Wr(", "event taint", "secondary writes"):
            self.assertNotIn(fragment.lower(), SYSTEM.lower())
        for workflow in self.workflows:
            public = json.loads(messages_for(workflow)[1]["content"])
            self.assertEqual(set(public), {"description", "labels", "tools", "policy"})
            for tool in public["tools"]:
                self.assertEqual(set(tool), {"agent", "tool", "params", "description"})

    @patch.dict("os.environ", {"SAGE_API_KEY": "test-only", "SAGE_API_BASE_URL": "https://example.invalid/v1"})
    @patch("urllib.request.urlopen", side_effect=OSError("sensitive transport detail"))
    def test_api_failure_has_no_retry_or_secret(self, opener):
        result = request_once([], "test-model", 0.2, 8192)
        self.assertEqual(opener.call_count, 1)
        self.assertEqual(result["transport_status"], "API_ERROR")
        self.assertNotIn("sensitive", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
