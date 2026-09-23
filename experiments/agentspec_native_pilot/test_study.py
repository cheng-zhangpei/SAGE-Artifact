import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import study


FROZEN = Path(__file__).parents[2] / 'artifacts/fse2027/agentspec_mimo72'


class StudyTests(unittest.TestCase):
    def test_full_suite_is_frozen_72(self):
        cases = study.select_cases('full72')
        self.assertEqual(72, len(cases))
        self.assertEqual(72, len({case['id'] for case in cases}))
        self.assertEqual(36, sum(case['layer'] == 'base' for case in cases))
        self.assertEqual(36, sum(case['layer'] == 'composition' for case in cases))

    def test_rejects_external_effects(self):
        with self.assertRaises(ValueError):
            study.validate_source('import os\ndef pilot_candidate(user_input, tool_input, intermediate_steps):\n    return os.system("bad")\n')
        with self.assertRaises(ValueError):
            study.validate_source('def pilot_candidate(user_input, tool_input, intermediate_steps):\n    user_input["trusted_event_labels"] = []\n    return False\n')

    def test_original_parameter_decisions(self):
        predicate = study.validate_source('import json\ndef pilot_candidate(user_input, tool_input, intermediate_steps):\n    p = json.loads(tool_input)\n    return p["destination"] == "external" and "SECRET" in user_input["trusted_event_labels"]\n')
        for destination in ('internal', 'external'):
            self.assertEqual(destination == 'external', predicate({'trusted_event_labels': ['SECRET']}, json.dumps({'destination': destination}), []))

    def test_pure_string_concatenation(self):
        predicate = study.validate_source('import json\ndef pilot_candidate(user_input, tool_input, intermediate_steps):\n    p = json.loads(tool_input)\n    return "slot:" + p.get("target") == "slot:external"\n')
        self.assertTrue(predicate({}, json.dumps({'target': 'external'}), []))

    def test_pure_type_check(self):
        predicate = study.validate_source('def pilot_candidate(user_input, tool_input, intermediate_steps):\n    labels = user_input.get("trusted_event_labels", [])\n    return isinstance(labels, set)\n')
        self.assertFalse(predicate({'trusted_event_labels': []}, '{}', []))

    def test_narrow_json_parse_exception(self):
        predicate = study.validate_source('import json\ndef pilot_candidate(user_input, tool_input, intermediate_steps):\n    try:\n        p = json.loads(tool_input)\n    except (json.JSONDecodeError, TypeError):\n        return False\n    return p.get("target") == "external"\n')
        self.assertTrue(predicate({}, json.dumps({'target': 'external'}), []))
        self.assertFalse(predicate({}, 'bad json', []))

    def test_pure_local_helper(self):
        predicate = study.validate_source('def pilot_candidate(user_input, tool_input, intermediate_steps):\n    labels = set(user_input.get("trusted_event_labels", []))\n    if labels:\n        def contains(label):\n            return label in labels\n        return contains("SECRET")\n    return False\n')
        self.assertTrue(predicate({'trusted_event_labels': ['SECRET']}, '{}', []))
        self.assertFalse(predicate({'trusted_event_labels': []}, '{}', []))
        with self.assertRaises(ValueError):
            study.validate_source('def pilot_candidate(user_input, tool_input, intermediate_steps):\n    def recurse():\n        return recurse()\n    return recurse()\n')

    def test_finite_local_iteration(self):
        predicate = study.validate_source('def pilot_candidate(user_input, tool_input, intermediate_steps):\n    labels = set()\n    labels.add("SECRET")\n    labels.update(set())\n    ordered = []\n    for label in labels:\n        ordered.append(label)\n    for label in ordered:\n        if label in user_input.get("trusted_event_labels", []):\n            return True\n        else:\n            pass\n    return False\n')
        self.assertTrue(predicate({'trusted_event_labels': ['SECRET']}, '{}', []))
        self.assertFalse(predicate({'trusted_event_labels': []}, '{}', []))

    def test_only_stray_terminal_brace_is_normalized(self):
        source = 'def pilot_candidate(user_input, tool_input, intermediate_steps):\n    return False\n}'
        normalized, record = study.normalize_candidate_source(source)
        self.assertIsNotNone(record)
        self.assertFalse(study.validate_source(normalized)({}, '{}', []))
        with self.assertRaises(SyntaxError):
            study.normalize_candidate_source('def pilot_candidate(:\n    return False')

    def test_actual_runtime_on_base_and_composition(self):
        frozen = FROZEN
        if not (frozen / 'runtime/src').is_dir():
            self.skipTest('Pinned AgentSpec runtime is fetched by run.py and is not vendored')
        for task in ('W01', 'COMP-SUP-08', 'COMP-CLINICAL-REFERRAL-48'):
            with tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp)
                (folder / 'task.json').write_bytes((frozen / 'tasks' / task / 'task.json').read_bytes())
                (folder / 'response.json').write_text(json.dumps({'raw_content': json.dumps({'python': 'def pilot_candidate(user_input, tool_input, intermediate_steps):\n    return False\n'})}), encoding='utf-8')
                result = subprocess.run([sys.executable, str(Path(study.__file__)), '--output', str(frozen), '--worker', str(folder)], capture_output=True, text=True)
                self.assertEqual(0, result.returncode, result.stderr)
                metrics = json.loads((folder / 'evaluation.json').read_text())['metrics']
                self.assertEqual('FAIL', metrics['candidate']['status'])
                for arm in ('candidate_plus_sage', 'direct_sage'):
                    self.assertEqual('PASS', metrics[arm]['status'])
                    self.assertEqual(0, metrics[arm]['missed'])
                    self.assertEqual(0, metrics[arm]['blocked'])

    def test_candidate_runtime_error_is_unresolved(self):
        frozen = FROZEN
        if not (frozen / 'runtime/src').is_dir():
            self.skipTest('Pinned AgentSpec runtime is fetched by run.py and is not vendored')
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / 'task.json').write_bytes((frozen / 'tasks/W01/task.json').read_bytes())
            source = 'def pilot_candidate(user_input, tool_input, intermediate_steps):\n    labels = user_input["trusted_event_labels"]\n    return labels.issubset({"SECRET"})\n'
            (folder / 'response.json').write_text(json.dumps({'raw_content': json.dumps({'python': source})}), encoding='utf-8')
            result = subprocess.run([sys.executable, str(Path(study.__file__)), '--output', str(frozen), '--worker', str(folder)], capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stderr)
            evaluation = json.loads((folder / 'evaluation.json').read_text())
            self.assertEqual('UNKNOWN', evaluation['metrics']['candidate']['status'])
            self.assertEqual('UNKNOWN', evaluation['metrics']['candidate_plus_sage']['status'])
            self.assertEqual('PASS', evaluation['metrics']['direct_sage']['status'])
            self.assertGreater(len(evaluation['candidate_runtime_errors']), 0)


if __name__ == '__main__':
    unittest.main()
