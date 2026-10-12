"""Focused offline checks for the evidence-sensitivity diagnostic."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import evidence_sensitivity as experiment


class EvidenceSensitivityTests(unittest.TestCase):
    def test_frozen_selection_and_pending_approval(self):
        annotation = json.loads(experiment.ANNOTATIONS.read_text())
        self.assertEqual([case["row_index"] for case in annotation["cases"]],
                         list(experiment.SELECTED))
        status = experiment.approval_status(annotation)
        self.assertFalse(status["approved"])
        self.assertEqual(status["decisions"], {"pending_review": 17})

    def test_frozen_plan_validates_quotations_offsets_and_order(self):
        plan, _, _ = experiment.validate_plan()
        self.assertEqual(len(plan["items"]), 17)
        for item in plan["items"]:
            c = item["conditions"][experiment.CONDITIONS[2]]["passages"]
            d = item["conditions"][experiment.CONDITIONS[3]]["passages"]
            self.assertEqual(experiment.passage_multiset(c), experiment.passage_multiset(d))
            self.assertNotEqual(c, d)
            self.assertTrue(item["C_D_identity"]["same_sum_of_passage_chars"])

    def test_live_validation_is_locked_until_human_approval(self):
        with self.assertRaisesRegex(ValueError, "pending_review"):
            experiment.validate_plan(require_approval=True)

    def test_annotation_review_fields_do_not_change_evidence_hash(self):
        annotation = json.loads(experiment.ANNOTATIONS.read_text())
        before = experiment.annotation_spec_sha256(annotation)
        annotation["overall_status"] = "approved"
        annotation["reviewer"] = "Human reviewer"
        annotation["reviewed_utc"] = "2026-10-12T12:00:00+00:00"
        for case in annotation["cases"]:
            case["review_decision"] = "approved"
            case["reviewer_note"] = "checked"
        self.assertEqual(before, experiment.annotation_spec_sha256(annotation))
        self.assertTrue(experiment.approval_status(annotation)["approved"])

    def test_citation_verification_is_exact_and_source_local(self):
        passages = [{"page": 2, "text": "The exact decisive sentence.",
                     "source": "booklet", "pdf_sha256": "abc"}]
        verified, matches = experiment.citation_check(
            {"evidence_snippet": "exact decisive sentence"}, passages)
        self.assertTrue(verified)
        self.assertEqual(matches, passages)
        verified, matches = experiment.citation_check(
            {"evidence_snippet": "a paraphrase"}, passages)
        self.assertFalse(verified)
        self.assertEqual(matches, [])


if __name__ == "__main__":
    unittest.main()
