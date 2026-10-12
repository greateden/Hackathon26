"""Offline safeguards for the corrected diagnostic protocol."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import evidence_sensitivity_v2 as experiment


class EvidenceSensitivityV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = json.loads(experiment.PLAN.read_text())
        source = experiment.latest_by_key(experiment.read_jsonl(
            experiment.SOURCE / "predictions.jsonl"))["29:A_dense_baseline"]
        cls.legacy_record = dict(source, key="29:A_original", condition="A_original")
        # Reproduce the old v2 layout using immutable source telemetry, so tests
        # remain independent of the user's live output and its future progress.
        cls.legacy_record.pop("elapsed_s", None)

    def test_complete_block_rotation_rejects_old_reversal_and_metadata_change(self):
        item = next(i for i in self.plan["items"] if i["row_index"] == 432)
        conditions = copy.deepcopy(item["conditions"])
        minimal = conditions[experiment.CONDITIONS[1]]["passages"]
        distractors = conditions[experiment.CONDITIONS[2]]["passages"][len(minimal):]
        experiment.assert_block_rotation(item["claim"], minimal, distractors, conditions)
        conditions[experiment.CONDITIONS[3]]["passages"] = list(
            reversed(conditions[experiment.CONDITIONS[2]]["passages"]))
        with self.assertRaisesRegex(ValueError, "internal order"):
            experiment.assert_block_rotation(item["claim"], minimal, distractors, conditions)
        conditions = copy.deepcopy(item["conditions"])
        conditions[experiment.CONDITIONS[3]]["passages"][0]["page"] += 1
        with self.assertRaises(ValueError):
            experiment.assert_block_rotation(item["claim"], minimal, distractors, conditions)

    def test_frozen_sources_and_zero_network_dry_run(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            with patch.object(experiment, "connect", side_effect=AssertionError("inference")) as connect, \
                 patch("requests.sessions.Session.request", side_effect=AssertionError("network")) as request, \
                 patch("socket.socket.connect", side_effect=AssertionError("network")) as socket_connect, \
                 patch.object(experiment, "output_path", return_value=out):
                self.assertEqual(experiment.main(["dry-run"]), 0)
            connect.assert_not_called()
            request.assert_not_called()
            socket_connect.assert_not_called()
            manifest = json.loads((out / "manifest.json").read_text())
            self.assertEqual(manifest["inference_calls"], 0)
            self.assertEqual(manifest["planned_calls"], 60)
            self.assertEqual((out / "predictions.jsonl").read_bytes(), b"")

    def test_exclusions_and_independent_review_gate(self):
        annotation = json.loads(experiment.ANNOTATIONS.read_text())
        self.assertEqual(self.plan["selection"]["excluded"], [455, 550])
        self.assertEqual(len(self.plan["adjudications"]), 17)
        self.assertEqual(len(self.plan["items"]), 15)
        # Test the pending state on a copy; the real external review may be approved.
        annotation["overall_status"] = "pending_independent_chatgpt_review"
        for case in annotation["cases"]:
            case["review_decision"] = "pending_review"
        self.assertFalse(experiment.approval_status(annotation)["approved"])
        before = experiment.annotation_spec_sha256(annotation)
        annotation.update(overall_status="confirmed_by_independent_chatgpt",
                          reviewer="Independent ChatGPT review, recorded by user",
                          reviewed_utc="2026-10-12T12:00:00+00:00")
        for case in annotation["cases"]:
            case["review_decision"] = "approved" if case["primary_analysis"] else "excluded"
        self.assertTrue(experiment.approval_status(annotation)["approved"])
        self.assertEqual(experiment.annotation_spec_sha256(annotation), before)
        annotation["cases"][5]["primary_analysis"] = True
        self.assertNotEqual(experiment.annotation_spec_sha256(annotation), before)
        self.assertFalse(experiment.approval_status(annotation)["approved"])

    def test_tampered_prompt_and_offsets_fail_frozen_validation(self):
        for field, value in (("message_sha256", "changed"), ("prompt_tokens_offline", -1)):
            changed = copy.deepcopy(self.plan)
            changed["items"][0]["conditions"][experiment.CONDITIONS[2]][field] = value
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "plan.json"
                path.write_text(json.dumps(changed))
                with self.assertRaisesRegex(ValueError, "offline reconstruction"):
                    experiment.validate_plan(path)
        changed = copy.deepcopy(self.plan["items"][0]["conditions"][experiment.CONDITIONS[1]]["passages"][0])
        row = experiment.load_rows(experiment.DEFAULT_DATA)[29]
        booklet = experiment.get_booklet(row)
        changed["page_char_start"] += 1
        with self.assertRaisesRegex(ValueError, "offsets"):
            experiment.verify_offsets(booklet, changed)

    def test_relative_absolute_annotations_and_project_escape(self):
        relative = experiment.ANNOTATIONS.relative_to(experiment.PROJECT_ROOT)
        for path in (relative, experiment.ANNOTATIONS):
            plan, _, approval = experiment.validate_plan(annotation_path=path)
            self.assertEqual(plan, self.plan)
            self.assertTrue(approval["approved"])
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory) / "annotations.json"
            with self.assertRaisesRegex(ValueError, "inside the project root"):
                experiment.resolve_annotations(outside)
            link = Path(directory) / "project"
            link.symlink_to(experiment.PROJECT_ROOT, target_is_directory=True)
            self.assertEqual(experiment.resolve_annotations(link / relative),
                             experiment.ANNOTATIONS.resolve())

    def test_legacy_nested_latency_summarises_without_rewriting_records(self):
        records = [copy.deepcopy(self.legacy_record)]
        original = copy.deepcopy(records)
        summary = experiment.records_summary(self.plan, records, "RUNNING")
        self.assertEqual(summary["completed"], 1)
        self.assertEqual(summary["missing"], 59)
        stats = summary["conditions"][experiment.CONDITIONS[0]]
        self.assertEqual(stats["mean_latency_s"], round(records[0]["result"]["elapsed_s"], 2))
        self.assertEqual(records, original)

    def test_missing_or_invalid_latency_remains_an_explicit_error(self):
        for value in (None, -1, float("nan"), float("inf"), True):
            record = {"key": "failed", "result": {"error": "endpoint_failure"}}
            if value is not None:
                record["elapsed_s"] = value
            with self.assertRaisesRegex(ValueError, "valid measured elapsed_s"):
                experiment.scoring_record(record)

    def test_mock_resume_preserves_completed_call_and_times_new_failures(self):
        plan = copy.deepcopy(self.plan)
        plan["items"] = plan["items"][:1]
        annotation = json.loads(experiment.ANNOTATIONS.read_text())
        approval = experiment.approval_status(annotation)
        manifest = {"schema": experiment.SCHEMA,
                    "contract_sha256": experiment.fingerprint({
                        "plan_sha256": experiment.sha256_file(experiment.PLAN),
                        "annotation_spec_sha256": experiment.annotation_spec_sha256(annotation),
                        "review": approval, "retries": 0}),
                    "plan_sha256": experiment.sha256_file(experiment.PLAN),
                    "sessions": []}
        metadata = {"model": plan["inference_contract"]["model"],
                    "revision": plan["inference_contract"]["revision"],
                    "instance_id": "offline-mock"}
        replies = [RuntimeError("mock failure")]
        for condition in experiment.CONDITIONS[2:]:
            replies.append({"label": "entailment", "usage": {"prompt_tokens":
                plan["items"][0]["conditions"][condition]["prompt_tokens_offline"]}})
        judge = Mock()
        judge.judge.side_effect = replies
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / "manifest.json").write_text(json.dumps(manifest))
            (out / "predictions.jsonl").write_text(json.dumps(self.legacy_record) + "\n")
            event = {k: v for k, v in self.legacy_record.items()
                     if k not in {"result", "pred", "correct", "status", "finished_utc"}}
            (out / "events.jsonl").write_text(json.dumps(event) + "\n")
            original_predictions = (out / "predictions.jsonl").read_bytes()
            original_events = (out / "events.jsonl").read_bytes()
            with patch.object(experiment, "validate_plan", return_value=(plan, annotation, approval)), \
                 patch.object(experiment, "output_path", return_value=out), \
                 patch.object(experiment, "connect", return_value=(judge, metadata)), \
                 patch.object(experiment.time, "perf_counter", side_effect=[10, 11.25, 20, 22, 30, 33]), \
                 patch("requests.sessions.Session.request", side_effect=AssertionError("network")) as network, \
                 patch("socket.socket.connect", side_effect=AssertionError("network")):
                self.assertEqual(experiment.main(["run", "--live", "--resume"]), 1)
            network.assert_not_called()
            self.assertEqual(judge.judge.call_count, 3)
            self.assertTrue((out / "predictions.jsonl").read_bytes().startswith(original_predictions))
            self.assertTrue((out / "events.jsonl").read_bytes().startswith(original_events))
            records = experiment.read_log(out / "predictions.jsonl")
            self.assertEqual([r["elapsed_s"] for r in records[1:]], [1.25, 2, 3])
            self.assertEqual(records[1]["status"], "failed")
            self.assertEqual(records[1]["result"]["error"], "experiment_error:RuntimeError")
            self.assertIsNone(records[1]["pred"])
            summary = json.loads((out / "summary.json").read_text())
            self.assertEqual((summary["completed"], summary["failed"], summary["missing"]), (3, 1, 0))
            stats = summary["conditions"][experiment.CONDITIONS[1]]
            self.assertEqual(stats["errors"], 1)
            self.assertEqual(stats["mean_latency_s_all"], 1.25)
            self.assertIsNone(stats["mean_latency_s"])
            updated = json.loads((out / "manifest.json").read_text())
            self.assertEqual(updated["contract_sha256"], manifest["contract_sha256"])
            self.assertEqual(updated["plan_sha256"], manifest["plan_sha256"])
            self.assertEqual(updated["sessions"][-1]["runner_sha256"],
                             experiment.sha256_file(Path(experiment.__file__)))


if __name__ == "__main__":
    unittest.main()
