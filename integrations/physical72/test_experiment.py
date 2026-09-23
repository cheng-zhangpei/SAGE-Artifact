import tempfile
import json
import unittest
from pathlib import Path

from integrations.physical72.experiment import SCENARIOS, WORKFLOWS, PhysicalSystem, source_location, run
from integrations.supportdesk.system import LocalCaptureServer


class Physical72Test(unittest.TestCase):
    def test_suite_balance_and_identity(self):
        self.assertEqual(72, len(WORKFLOWS))
        self.assertEqual(72, len({workflow.workflow_id for workflow in WORKFLOWS}))
        for scenario in SCENARIOS:
            rows = [workflow for workflow in WORKFLOWS if workflow.scenario == scenario]
            self.assertEqual(24, len(rows))
            self.assertEqual(12, sum(workflow.expected_physical_dangerous for workflow in rows))
            self.assertEqual(12, sum(not workflow.expected_physical_dangerous for workflow in rows))

    def test_persisted_mutation_controls_state_and_payload(self):
        # Changing backing storage after setup must change both observation and output.
        with tempfile.TemporaryDirectory() as temporary, LocalCaptureServer() as capture:
            system = PhysicalSystem(Path(temporary), capture)
            for identity in ("SUP01B", "SUP02B"):
                workflow = next(w for w in WORKFLOWS if w.workflow_id == identity)
                system.reset(workflow)
                item = workflow.sources[0]
                replacement = {"body": "backend-only-mutated-content", "labels": ["PII"]}
                if item.backing == "sqlite":
                    with system._connect() as db:
                        db.execute("UPDATE resources SET body=?, labels=? WHERE identity=?",
                                   (replacement["body"], json.dumps(replacement["labels"]), item.identity))
                else:
                    (system.files / f"{item.identity}.json").write_text(json.dumps(replacement), encoding="utf-8")
                self.assertEqual(frozenset({"PII"}), system.state(workflow).get(source_location(workflow, item)))
                system.execute(workflow)
                self.assertEqual(replacement["body"], capture.records[0]["body"]["body"])
                self.assertEqual(replacement["labels"], capture.records[0]["body"]["labels"])

    def test_real_side_effect_execution(self):
        with tempfile.TemporaryDirectory(prefix="sage_physical72_test_") as temporary:
            result = run(Path(temporary))
        metrics = {row["monitor"]: row for row in result["runtime_monitor_metrics"]}
        self.assertEqual(72, result["workflow_count"])
        self.assertEqual(1.0, metrics["sage"]["physical_DER"])
        self.assertEqual(3 / 36, metrics["sage"]["physical_BBR"])
        self.assertTrue(metrics["sage"]["denied_zero_side_effect"])
        self.assertEqual(3 / 36, metrics["context_only"]["physical_DER"])


if __name__ == "__main__":
    unittest.main()
