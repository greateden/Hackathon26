"""Focused offline contracts for the paired vote-aware evaluation."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import vote_aware_paired_eval as paired


class VoteAwarePairedContracts(unittest.TestCase):
    def test_selection_is_balanced_deterministic_subset(self):
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


if __name__ == "__main__":
    unittest.main()
