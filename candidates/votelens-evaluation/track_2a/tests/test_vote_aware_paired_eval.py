"""Focused offline contracts for the paired vote-aware evaluation."""
import json
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import vote_aware_paired_eval as paired


class VoteAwarePairedContracts(unittest.TestCase):
    def test_manifest_configuration_must_match_frozen_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            plan = {"configuration": {"model": paired.CSCS_MODEL}, "cases": []}
            manifest = {"schema": paired.SCHEMA, "configuration": dict(plan["configuration"]), "items": []}
            for index in range(54):
                case = {"row_index": index, "case_id": str(index), "gold": "neutral", "pdf_sha256": "pdf"}
                plan["cases"].append(case)
                manifest["items"].append(dict(case, arms={arm: {"passages": [{}] * 5,
                    "prompt_sha256": "prompt"} for arm in paired.ARMS}))
            (directory / paired.PLAN_NAME).write_text(json.dumps(plan))
            manifest["plan_sha256"] = paired.digest((directory / paired.PLAN_NAME).read_bytes())
            paired.validate_manifest(directory, plan, manifest)
            changed = copy.deepcopy(manifest)
            changed["configuration"]["model"] = "different-model"
            with self.assertRaisesRegex(ValueError, "configuration differs"):
                paired.validate_manifest(directory, plan, changed)

    def test_selection_is_balanced_deterministic_subset(self):
        if not paired.DEFAULT_DATA.exists():
            self.skipTest("requires data/eval/mnli_swiss_v1.1.jsonl")
        rows = paired.load_rows(paired.DEFAULT_DATA)
        source = json.loads(paired.SOURCE_PLAN.read_text())
        first = paired.selected_indices(rows, source)
        self.assertEqual(first, paired.selected_indices(rows, source))
        self.assertEqual(len(first), 54)
        self.assertEqual(len(set(first)), 54)

    def test_schedule_alternates_and_has_108_unique_calls(self):
        items = [{"row_index": i} for i in range(54)]
        calls = paired.schedule(items)
        self.assertEqual(len(calls), 108)
        self.assertEqual(len({(item["row_index"], arm) for item, arm in calls}), 108)
        self.assertEqual([arm for _, arm in calls[:2]], list(paired.ARMS))
        self.assertEqual([arm for _, arm in calls[2:4]], list(reversed(paired.ARMS)))

    def test_failures_count_in_denominator(self):
        records = []
        for i in range(3):
            records.append({"arm": paired.FROZEN_PIPELINE, "gold": "entailment",
                            "pred": "entailment" if i == 0 else None,
                            "strict_correct": i == 0, "raw_correct": i < 2,
                            "valid_output": i == 0,
                            "result": {"error": None if i == 0 else "failure", "usage": {}}})
        metrics = paired.arm_metrics(records)
        self.assertEqual(metrics["n"], 3)
        self.assertEqual(metrics["accuracy"], 0.333)
        self.assertEqual(metrics["valid_output_rate"], 0.3333)
        self.assertEqual(metrics["raw_label_accuracy"], 0.6667)

    def test_exact_paired_test(self):
        self.assertEqual(paired.binomial_two_sided(0, 0), 1.0)
        self.assertEqual(paired.binomial_two_sided(0, 5), 0.0625)
        self.assertEqual(paired.binomial_two_sided(2, 2), 1.0)

    def test_only_transport_failures_are_retryable(self):
        self.assertTrue(paired.transient({"error": "endpoint_or_tokenisation_error:ConnectionError"}))
        self.assertTrue(paired.transient({"error": "endpoint_or_tokenisation_error:Timeout"}))
        self.assertFalse(paired.transient({"error": "model_response_parse_error:JSONDecodeError"}))
        self.assertFalse(paired.transient({"error": "invalid_vote_status"}))

    def test_jsonl_resume_contract_rejects_duplicate_attempts(self):
        items = [{"row_index": i} for i in range(54)]
        manifest = {"items": items}
        event = {"schema": paired.SCHEMA, "key": "0:" + paired.FROZEN_PIPELINE,
                 "attempt_id": "attempt-1"}
        record = dict(event, status="failed")
        paired.validate_logs(manifest, [record], [event])
        with self.assertRaisesRegex(ValueError, "duplicate event attempt"):
            paired.validate_logs(manifest, [record], [event, dict(event)])

    def test_prediction_must_match_its_event_identity(self):
        manifest = {"items": [{"row_index": 0}, {"row_index": 1}]}
        event = {"schema": paired.SCHEMA, "key": "0:dense-v1",
                 "attempt_id": "attempt-1", "row_index": 0,
                 "arm": "dense-v1", "gold": "neutral", "case_id": "case-0",
                 "attempt_number": 1, "configured_model": paired.CSCS_MODEL}
        for changes in ({"key": "1:vote-aware-v1"}, {"gold": "entailment"},
                        {"arm": "vote-aware-v1"}, {"row_index": 1},
                        {"case_id": "case-1"}, {"attempt_number": 2},
                        {"configured_model": "different-model"}):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "event identity"):
                paired.validate_logs(manifest, [dict(event, status="failed", **changes)], [event])

    def test_partial_summary_does_not_report_a_full_plan_paired_estimate(self):
        item = {"row_index": 0, "case_id": "case-0", "gold": "neutral",
                "request": {"claim_language": "de", "booklet_language": "fr"}}
        records = [{"key": "0:" + arm, "arm": arm, "gold": "neutral",
                    "pred": "neutral" if arm == paired.FROZEN_PIPELINE else None,
                    "strict_correct": arm == paired.FROZEN_PIPELINE,
                    "status": "completed" if arm == paired.FROZEN_PIPELINE else "failed",
                    "result": {}} for arm in paired.ARMS]
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / "predictions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
            summary = paired.summarise_run(directory, {"items": [item]})
        self.assertEqual(summary["paired"]["n"], 1)
        self.assertIsNone(summary["paired"]["accuracy_difference"])
        self.assertIsNone(summary["paired"]["mcnemar_exact_p"])


if __name__ == "__main__":
    unittest.main()
