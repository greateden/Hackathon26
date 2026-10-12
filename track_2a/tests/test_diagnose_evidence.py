"""Focused offline checks for the evidence diagnostic and Oracle plan."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import diagnose_evidence as diagnosis
from booklet_app import classify


class EvidenceDiagnosisTests(unittest.TestCase):
    def test_statuses_and_deterministic_controls(self):
        completed = {"status": "completed", "pred": "neutral", "correct": True, "result": {}}
        self.assertEqual(diagnosis.case_status(completed), "correct")
        self.assertEqual(diagnosis.case_status(dict(completed, correct=False)), "incorrect")
        self.assertEqual(diagnosis.case_status({"status": "failed", "pred": None,
                         "result": {"error": "incomplete_completion"}}), "incomplete")
        self.assertEqual(diagnosis.case_status({"status": "failed", "pred": None,
                         "result": {"error": "unparseable_response"}}), "invalid")
        latest = {}
        rows = [(9, "entailment"), (2, "entailment"), (8, "neutral"), (7, "contradiction")]
        for index, gold in rows:
            latest[f"{index}:retrieved"] = {"row_index": index, "status": "completed", "correct": True,
                                             "gold": gold, "result": {"citation_verified": True}}
        self.assertEqual(diagnosis.select_controls([9, 2, 8, 7], latest), [2, 8, 7])

    def test_oracle_request_sends_claim_and_reference_not_evaluation_metadata(self):
        item = {"claim": "Claim", "claim_language": "de", "reference": "Genuine reference",
                "reference_language": "fr", "gold": "contradiction", "role": "diagnostic_error",
                "retrieved_prediction": "entailment", "row_index": 3}
        request = diagnosis.oracle_request(item)
        self.assertNotIn("gold", request)
        self.assertNotIn("role", request)
        judge = Mock()
        judge.judge.return_value = {"label": "neutral", "label_code": 1,
                                   "evidence_snippet": "Genuine reference"}
        result = classify(request, judge)
        judge.judge.assert_called_once_with("Claim", "Genuine reference", seed=diagnosis.SEED)
        self.assertTrue(result["citation_verified"])

    def test_oracle_plan_validation_is_offline_and_bound_to_dataset(self):
        row = {"claim": "Claim", "claim_language": "de", "reference_string": "Reference evidence",
               "reference_language": "fr", "entailment_label": 1, "booklet_url": "https://example.test/a.pdf",
               "vote": "Vote", "baseline_score": 0, "booklet_publish_date": "2026-01-01",
               "booklet_download_date": "2026-01-02"}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / "dataset.jsonl"
            data.write_text(json.dumps(row) + "\n")
            relative_name = str(data.relative_to(root))
            plan = {"schema": diagnosis.ORACLE_SCHEMA,
                    "source_identities": {relative_name: diagnosis.sha256_file(data)},
                    "selection": {"n": 1, "error_cases": 1, "controls": []},
                    "inference_contract": {"max_tokens": 512, "temperature": 0, "seed": diagnosis.SEED,
                                           "parser_version": diagnosis.RECORDED_PARSER_VERSION,
                                           "system_prompt_sha256": diagnosis.digest(diagnosis.build_messages(
                                               "CLAIM", "EVIDENCE")[0]["content"].encode())},
                    "items": [{"row_index": 0, "role": "diagnostic_error", "claim": row["claim"],
                               "claim_language": row["claim_language"], "reference": row["reference_string"],
                               "reference_language": row["reference_language"],
                               "reference_sha256": diagnosis.digest(row["reference_string"].encode()),
                               "gold": "neutral", "reference_flags": diagnosis.reference_flags(row["reference_string"])}]}
            plan_path = root / "oracle.json"
            plan_path.write_text(json.dumps(plan))
            with patch.object(diagnosis, "PROJECT_ROOT", root), patch.object(
                    diagnosis, "build_messages", wraps=diagnosis.build_messages) as messages:
                checked = diagnosis.validate_oracle_plan(plan_path, data)
            self.assertEqual(len(checked["items"]), 1)
            self.assertGreater(messages.call_count, 0)

    def test_oracle_run_is_append_only_and_resume_safe(self):
        row = {"claim": "Claim", "claim_language": "de", "reference_string": "Reference evidence",
               "reference_language": "fr", "entailment_label": 1, "booklet_url": "https://example.test/a.pdf",
               "vote": "Vote", "baseline_score": 0, "booklet_publish_date": "2026-01-01",
               "booklet_download_date": "2026-01-02"}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / "dataset.jsonl"
            data.write_text(json.dumps(row) + "\n")
            contract = {"model": "m1rkocasu/Apertus-v1.5-8B-text-MLX-6bit", "revision": "rev",
                        "context_tokens": 81920, "max_tokens": 512, "temperature": 0,
                        "seed": diagnosis.SEED, "parser_version": diagnosis.RECORDED_PARSER_VERSION,
                        "system_prompt_sha256": diagnosis.digest(diagnosis.build_messages(
                            "CLAIM", "EVIDENCE")[0]["content"].encode())}
            plan = {"schema": diagnosis.ORACLE_SCHEMA,
                    "source_identities": {str(data.relative_to(root)): diagnosis.sha256_file(data)},
                    "selection": {"n": 1, "error_cases": 1, "controls": []},
                    "inference_contract": contract,
                    "items": [{"row_index": 0, "role": "diagnostic_error", "claim": row["claim"],
                               "claim_language": row["claim_language"], "reference": row["reference_string"],
                               "reference_language": row["reference_language"],
                               "reference_sha256": diagnosis.digest(row["reference_string"].encode()),
                               "gold": "neutral", "retrieved_prediction": "entailment",
                               "reference_flags": diagnosis.reference_flags(row["reference_string"])}]}
            plan_path = root / "oracle.json"
            plan_path.write_text(json.dumps(plan))
            out = root / "oracle-run"
            args = SimpleNamespace(oracle_plan=plan_path, data=data, context=81920,
                                   endpoint="http://127.0.0.1:8080", out=out, resume=False,
                                   retry_failed=False, retries=1, timeout=180)
            metadata = {"model": contract["model"], "revision": "rev", "instance_id": "test"}
            result = {"label": "neutral", "label_code": 1, "evidence_snippet": "Reference evidence",
                      "citation_verified": True, "error": None}
            def local_output(path):
                path.mkdir(parents=True, exist_ok=True)
                return path
            with patch.object(diagnosis, "PROJECT_ROOT", root), \
                 patch.object(diagnosis, "output_path", side_effect=local_output), \
                 patch.object(diagnosis, "connect", return_value=(Mock(), metadata)), \
                 patch.object(diagnosis, "classify", return_value=result) as model:
                self.assertEqual(diagnosis.run_oracle(args), 0)
                self.assertEqual(model.call_count, 1)
                args.resume = True
                model.reset_mock()
                self.assertEqual(diagnosis.run_oracle(args), 0)
                model.assert_not_called()
            self.assertEqual(len(diagnosis.read_jsonl(out / "predictions.jsonl")), 1)

    def test_recorded_v3_parser_is_pinned_despite_current_v31_policy(self):
        raw = '{"meta":{"label":"entailment"},"label":"neutral-ish"}'
        result = diagnosis.apply_recorded_parser({"raw_response": raw,
                                                  "error": "unparseable_response", "label": None})
        self.assertEqual(result["label"], "entailment")
        self.assertEqual(result["parser_version"], "label-parse-v3-strict")
        self.assertNotIn("error", result)


if __name__ == "__main__":
    unittest.main()
