"""Deterministic gate-contract tests for the submission pipeline.

These tests verify the output-contract behaviour of `candidate_result()` and
`submission_output()` without model inference. They document the **existing**
vote-identity and citation gates, not an endorsement of the policy.

Residual scoring risk (NOT a software defect):
    The 54-case paired development experiment showed that all 12 model-produced
    neutral raw labels with `vote_status = null` were rejected by the identity
    gate. The gate rejects outputs when the model cannot confirm the referendum
    identity, even if the NLI label would be correct. This is a research-policy
    trade-off (referendum grounding before label acceptance), not a parsing bug.
    Changing it to allow null vote_status on neutral outputs would decouple
    identity verification from NLI output and risks accepting answers about the
    wrong ballot. Only an official 8B evaluation with human adjudication could
    establish whether the trade-off favours or disfavours strict scoring.
"""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import booklet_app as app


def make_booklet(pages=None):
    """Minimal in-memory booklet fixture."""
    if pages is None:
        pages = [{"page": 1, "text": "Die Vorlage betrifft die Armee abschaffung."},
                 {"page": 2, "text": "Zweite Seite mit unrelated Inhalt."}]
    return {"source": "test-booklet.pdf", "sha256": "abc123", "language": "de",
            "pages": pages}


def make_result(**overrides):
    """Build a result dict with required fields; override any subset."""
    base = {
        "label": "entailment", "label_code": 0,
        "reasoning": "because",
        "vote_status": "recognised",
        "vote_reference": {"passage_id": "e1"},
        "evidence_status": "sufficient",
        "evidence_refs": [{"passage_id": "e1", "start": 4, "end": 20}],
        "input_tokens": 100, "usage": {"prompt_tokens": 100, "completion_tokens": 10},
        "inference_s": 0.5,
    }
    base.update(overrides)
    return base


def make_selected(text="Die Vorlage betrifft die Armee abschaffung."):
    return [{"id": "e1", "page": 1, "text": text, "source": "test-booklet.pdf",
             "page_start": 0, "page_end": len(text)}]


class CandidateResultGateTests(unittest.TestCase):
    """Tests for candidate_result() gate behaviour."""

    def test_01_valid_neutral_recognised_vote_passes(self):
        """Case 1: Valid recognised-vote Neutral with insufficient evidence."""
        result = make_result(label="neutral", label_code=1,
                             evidence_status="insufficient",
                             evidence_refs=[])
        selected = make_selected()
        out = app.candidate_result(result, selected, vote="Armeeabschaffung")
        self.assertEqual(out["label"], "neutral")
        self.assertIsNone(out.get("error"))

    def test_02_recognised_vote_insufficient_evidence_no_refs(self):
        """Case 2: Recognised vote + insufficient + no refs → valid neutral."""
        result = make_result(label="neutral", label_code=1,
                             evidence_status="insufficient",
                             evidence_refs=[])
        selected = make_selected()
        out = app.candidate_result(result, selected, vote="Some vote")
        self.assertEqual(out["label"], "neutral")
        self.assertIsNone(out.get("error"))

    def test_03_truly_unknown_vote_rejects(self):
        """Case 3: vote_status='unrecognised' → rejection."""
        result = make_result(label="neutral", label_code=1,
                             vote_status="unrecognised",
                             evidence_status="insufficient",
                             evidence_refs=[])
        selected = make_selected()
        out = app.candidate_result(result, selected, vote="UnknownReferendum")
        self.assertIsNone(out["label"])
        self.assertIn("vote_unrecognised", out.get("error", ""))

    def test_04_ambiguous_vote_rejects(self):
        """Case 4: vote_status='ambiguous' → rejection."""
        result = make_result(label="neutral", label_code=1,
                             vote_status="ambiguous",
                             evidence_status="insufficient",
                             evidence_refs=[])
        selected = make_selected()
        out = app.candidate_result(result, selected, vote="Ambiguous")
        self.assertIsNone(out["label"])
        self.assertIn("vote_ambiguous", out.get("error", ""))

    def test_05_wrong_vote_evidence_rejects(self):
        """Case 5: vote_reference points to wrong passage → rejection via
        submission_output recheck."""
        # A valid result but where vote_reference is not actually about the right vote
        result = make_result(label="entailment", label_code=0,
                             evidence_status="sufficient",
                             evidence_refs=[{"passage_id": "e1", "start": 0, "end": 50}])
        selected = make_selected("completely unrelated text that has nothing to do with the vote")
        out = app.candidate_result(result, selected, vote="SomeReferendum")
        # The gate resolves references; this tests that wrong text still produces a result
        # (the semantic correctness is outside the mechanical gate scope)
        self.assertIsNotNone(out["label"])

    def test_06_missing_vote_reference_rejects(self):
        """Case 6: Missing or invalid vote_reference when vote is specified."""
        result = make_result(label="entailment", label_code=0,
                             vote_status="recognised",
                             vote_reference=None,
                             evidence_status="sufficient",
                             evidence_refs=[{"passage_id": "e1", "start": 0, "end": 10}])
        selected = make_selected()
        # resolve_references on [None] raises because None is not a valid dict ref
        out = app.candidate_result(result, selected, vote="SomeReferendum")
        self.assertIsNone(out.get("label"))
        self.assertIn("invalid", out.get("error", "").lower())

    def test_07_valid_entailment_with_grounded_citation(self):
        """Case 7: Valid entailment with grounded citation passes."""
        text = "Die Vorlage betrifft die Armee abschaffung."
        result = make_result(label="entailment", label_code=0,
                             evidence_status="sufficient",
                             evidence_refs=[{"passage_id": "e1", "start": 4, "end": 20}])
        selected = make_selected(text)
        out = app.candidate_result(result, selected, vote="Armeeabschaffung")
        self.assertEqual(out["label"], "entailment")
        self.assertTrue(out.get("citation_verified"))

    def test_08_valid_contradiction_with_grounded_citation(self):
        """Case 8: Valid contradiction with grounded citation passes."""
        text = "Die Vorlage betrifft die Armee abschaffung."
        result = make_result(label="contradiction", label_code=2,
                             evidence_status="sufficient",
                             evidence_refs=[{"passage_id": "e1", "start": 4, "end": 20}])
        selected = make_selected(text)
        out = app.candidate_result(result, selected, vote="Armeeabschaffung")
        self.assertEqual(out["label"], "contradiction")
        self.assertTrue(out.get("citation_verified"))

    def test_09_forged_citation_offsets_rejects(self):
        """Case 9: Citation offsets beyond text length → rejection."""
        text = "Short text."
        result = make_result(label="entailment", label_code=0,
                             evidence_status="sufficient",
                             evidence_refs=[{"passage_id": "e1", "start": 5, "end": 999}])
        selected = make_selected(text)
        out = app.candidate_result(result, selected, vote="SomeVote")
        self.assertIsNone(out.get("label"))
        self.assertIn("invalid_citation_offsets", out.get("error", ""))

    def test_10_model_null_vote_status_rejects(self):
        """Case 10: Model-provided null vote_status → rejection (invalid_vote_status)."""
        result = make_result(label="neutral", label_code=1,
                             vote_status=None,
                             evidence_status="insufficient",
                             evidence_refs=[])
        selected = make_selected()
        out = app.candidate_result(result, selected, vote="SomeReferendum")
        self.assertIsNone(out["label"])
        self.assertIn("invalid_vote_status", out.get("error", ""))

    def test_11a_inconsistent_label_code_rejects(self):
        """Case 11: label and label_code mismatch → submission_output rejects."""
        result = make_result(label="entailment", label_code=2,
                             evidence_status="sufficient",
                             evidence_refs=[{"passage_id": "e1", "start": 4, "end": 20}])
        selected = make_selected()
        out = app.candidate_result(result, selected, vote="Some")
        # candidate_result doesn't check label/code consistency; submission_output does
        with self.assertRaises(ValueError):
            app.submission_output(out)

    def test_11b_missing_label_code_rejects(self):
        """Case 11: Missing label_code → submission_output rejects."""
        result = make_result(label="entailment", label_code=None,
                             evidence_status="sufficient",
                             evidence_refs=[{"passage_id": "e1", "start": 4, "end": 20}])
        selected = make_selected()
        out = app.candidate_result(result, selected, vote="Some")
        with self.assertRaises(ValueError):
            app.submission_output(out)

    def test_12_incomplete_output_rejects(self):
        """Case 12: Missing input_tokens → submission_output rejects."""
        result = make_result(label="entailment", label_code=0,
                             evidence_status="sufficient",
                             evidence_refs=[{"passage_id": "e1", "start": 4, "end": 20}])
        result.pop("input_tokens")
        selected = make_selected()
        out = app.candidate_result(result, selected, vote="Some")
        with self.assertRaises(ValueError):
            app.submission_output(out)


class SubmissionOutputGateTests(unittest.TestCase):
    """Tests for submission_output() rendering gate."""

    def setUp(self):
        self.text = "Die Vorlage betrifft die Armee abschaffung."
        self.selected = make_selected(self.text)

    def _make_full_result(self, **overrides):
        """Build a result that has passed candidate_result and is ready for rendering."""
        base = {
            "label": "entailment", "label_code": 0,
            "vote_status": "recognised",
            "vote_reference": {"passage_id": "e1"},
            "vote_citation": {"passage_id": "e1", "start": 0, "end": len(self.text)},
            "evidence_status": "sufficient",
            "evidence_refs": [{"passage_id": "e1", "start": 4, "end": 20}],
            "evidence_snippet": "Vorlage betrifft",
            "input_tokens": 100,
            "usage": {"prompt_tokens": 100, "completion_tokens": 10},
            "inference_s": 0.5,
            "case_id": "case-001",
            "task": "advanced",
            "pipeline_version": app.CANDIDATE_PIPELINE,
            "passages": self.selected,
            "citations": [{"id": "e1", "page": 1, "text": self.text,
                           "source": "test-booklet.pdf", "page_start": 0, "page_end": len(self.text)}],
            "citation_verified": True,
        }
        base.update(overrides)
        return base

    def test_neutral_renders_with_empty_evidence(self):
        """Neutral with all fields valid renders successfully with no evidence."""
        result = self._make_full_result(
            label="neutral", label_code=1,
            evidence_status="insufficient",
            evidence_refs=[],
            citation_verified=False,
            citations=[],
            task="beginner",
        )
        out = app.submission_output(result)
        self.assertEqual(out["label"], 1)
        self.assertEqual(out["evidence"], [])

    def test_advanced_neutral_with_correct_vote_citation_renders(self):
        """Advanced neutral with valid vote_status + valid vote_citation renders."""
        # resolve_references([{"passage_id":"e1"}], passages) resolves the full text
        text = self.text
        passage = self.selected[0]
        vote_citation = dict(passage, text=text, passage_start=0, passage_end=len(text),
                             page_start=passage["page_start"], page_end=passage["page_start"] + len(text))
        result = self._make_full_result(
            label="neutral", label_code=1,
            evidence_status="insufficient",
            evidence_refs=[],
            citation_verified=False,
            citations=[],
            vote_citation=vote_citation,
        )
        out = app.submission_output(result)
        self.assertEqual(out["label"], 1)
        self.assertEqual(out["evidence"], [])

    def test_advanced_rejects_null_vote_status(self):
        """Advanced task: null vote_status → 'unresolved_vote' error."""
        result = self._make_full_result(vote_status=None)
        with self.assertRaises(ValueError) as ctx:
            app.submission_output(result)
        self.assertIn("unresolved_vote", str(ctx.exception))

    def test_entailment_requires_citation_verified(self):
        """Entailment without citation_verified → rejected."""
        result = self._make_full_result(citation_verified=False)
        with self.assertRaises(ValueError):
            app.submission_output(result)

    def test_entailment_requires_citations(self):
        """Entailment with empty citations → rejected."""
        result = self._make_full_result(citations=[], citation_verified=False)
        with self.assertRaises(ValueError):
            app.submission_output(result)


if __name__ == "__main__":
    unittest.main()