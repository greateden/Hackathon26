#!/usr/bin/env python3
"""Provenance guard: verify that the courage-to-be-wrong experience
does not present AI-generated interpretation as independent human verification.

Run from the repo root:
    PYTHONPATH=src python3 -m unittest tests/test_courage_provenance.py
"""
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
FACTS = HERE.parent / "docs" / "experience" / "courage-to-be-wrong" / "facts.json"
APP_JS = HERE.parent / "docs" / "experience" / "courage-to-be-wrong" / "app.js"
COURAGE_PY = HERE.parent / "docs" / "experience" / "courage-to-be-wrong" / "courage_data.py"

VALID_CITATION_STATUSES = {
    "NOT_REACHED", "NO_CITATION", "CITATION_UNVERIFIABLE",
    "CITATION_MECHANICAL_FAIL", "CITATION_OCCURS_SEMANTIC_UNVERIFIED",
    "NOT REACHED",  # fallback for cases without computed status
}

FORBIDDEN_PHRASES = [
    "Human-authored",
    "human-authored",
    "independently verified",
    "independent human review",  # only valid when preceded by "No" or "not"
    "This proves that no relevant evidence exists",
    "contradiction therefore absent elsewhere",
]


class TestProvenance(unittest.TestCase):
    """The provenance layer must not imply independent human fact-checking."""

    def setUp(self):
        if not FACTS.exists():
            self.skipTest(f"{FACTS} not found (clean checkout, facts not generated)")
        with FACTS.open(encoding="utf-8") as f:
            self.data = json.load(f)

    def test_gallery_no_human_authored_claim(self):
        """Gallery annotation_provenance must not say 'Human-authored'."""
        gallery = self.data.get("failure_gallery")
        if gallery is None:
            self.skipTest("raw tree absent; gallery not regenerated")
        for card in gallery:
            prov = card.get("annotation_provenance", "")
            self.assertNotIn("Human-authored", prov,
                             f"{card['case_id']} still claims Human-authored")
            self.assertNotIn("human-authored", prov)

    def test_passport_no_human_authored_claim(self):
        """Passport annotation_provenance must not imply human verification."""
        passports = self.data.get("evidence_passport")
        if passports is None:
            self.skipTest("raw tree absent; passports not regenerated")
        for p in passports:
            prov = p.get("annotation_provenance", "")
            self.assertNotIn("Human-authored", prov,
                             f"{p['case_id']} still claims Human-authored")

    def test_passport_has_trust_status(self):
        """Passports must carry an explicit annotation_trust_status field."""
        passports = self.data.get("evidence_passport")
        if passports is None:
            self.skipTest("raw tree absent; passports not regenerated")
        for p in passports:
            status = p.get("annotation_trust_status")
            self.assertIsNotNone(
                status,
                f"{p['case_id']}: missing annotation_trust_status")
            self.assertIn("NOT INDEPENDENTLY VERIFIED", status,
                          f"{p['case_id']}: trust status does not declare "
                          "non-independence")

    def test_passport_requires_human_review(self):
        """All passports must flag requires_human_review=True."""
        passports = self.data.get("evidence_passport")
        if passports is None:
            self.skipTest("raw tree absent; passports not regenerated")
        for p in passports:
            self.assertTrue(p.get("requires_human_review"),
                            f"{p['case_id']}: requires_human_review should be True")

    def test_citation_status_valid(self):
        """Citation status must be one of the five defined states."""
        passports = self.data.get("evidence_passport")
        if passports is None:
            self.skipTest("raw tree absent; passports not regenerated")
        for p in passports:
            per = p.get("arms") or p.get("conditions") or {}
            for name, e in per.items():
                cs = e.get("citation_mechanical", "")
                self.assertIn(cs, VALID_CITATION_STATUSES,
                              f"{p['case_id']}/{name}: unexpected citation "
                              f"status {cs!r}")

    def test_neutral_scope_no_forbidden_inference(self):
        """Neutral-gold scope must not claim booklet-wide absence is proven."""
        passports = self.data.get("evidence_passport")
        if passports is None:
            self.skipTest("raw tree absent; passports not regenerated")
        for p in passports:
            scope = p.get("insufficiency_scope", "")
            for phrase in ["This proves that no relevant evidence exists",
                           "therefore absent elsewhere"]:
                self.assertNotIn(phrase, scope)

    def test_semantic_review_not_available(self):
        """semantic_sufficiency_status must say NOT ADJUDICATED or NOT ANNOTATED."""
        passports = self.data.get("evidence_passport")
        if passports is None:
            self.skipTest("raw tree absent; passports not regenerated")
        for p in passports:
            s = p.get("semantic_sufficiency_status", "")
            self.assertTrue(
                "NOT ADJUDICATED" in s or "NOT ANNOTATED" in s,
                f"{p['case_id']}: semantic_sufficiency_status should indicate "
                "no independent review, got: {s!r}")


class TestCourageDataSource(unittest.TestCase):
    """Source-code-level guards (work even without facts.json)."""

    def test_no_human_authored_in_source(self):
        if not COURAGE_PY.exists():
            self.skipTest("courage_data.py not found")
        src = COURAGE_PY.read_text(encoding="utf-8")
        # The only acceptable occurrence is in the provenance header description
        # explaining what was previously wrong, not as a live claim.
        occurrences = [i for i, line in enumerate(src.split("\n"), 1)
                       if "Human-authored" in line]
        for line_no in occurrences:
            line = src.split("\n")[line_no - 1]
            # Allow comments/docstrings that describe the *absence* or correction
            self.assertTrue(
                "#" in line or '"' in line and "not" in line.lower(),
                f"courage_data.py line {line_no}: live 'Human-authored' claim: "
                f"{line!r}")

    def test_no_forbidden_phrases_in_app_js(self):
        if not APP_JS.exists():
            self.skipTest("app.js not found")
        src = APP_JS.read_text(encoding="utf-8")
        # "Human-authored" should not appear in the rendering code
        self.assertNotIn("Human-authored", src)


class TestCitationStatusHelpers(unittest.TestCase):
    """Behavioural tests for the two five-state citation-status classifiers.

    These lock the branch contract of ``_citation_status_paired()`` and
    ``_citation_status_sensitivity()`` in ``courage_data.py``. The five states
    are defined in ``attribution-verification.md`` §0.2; the *reachable* set is
    bounded by the real execution paths, which were read before writing them:

      * paired (source-selection-v1, ``booklet_app.candidate_result`` /
        ``submission_output``): the identity gate runs before the citation
        check, so a rejected output never reaches citation matching ->
        NOT_REACHED. A rejection is therefore NOT shown as a citation failure.
      * sensitivity (``citation_check`` always runs on a completed reply): a
        False result with a quoted snippet means the snippet was produced but
        did not occur in any supplied passage -> CITATION_MECHANICAL_FAIL; with
        no snippet there was nothing to match -> NO_CITATION.

    The helpers deliberately expose no ``CITATION_UNVERIFIABLE``/"unknown"
    state, because none is reachable from these records: the source evidence is
    always supplied, and a missing quotation is "not offered", not
    "unverifiable". Test 5 pins that so a fabricated state cannot slip in.
    """

    @classmethod
    def setUpClass(cls):
        if not COURAGE_PY.exists():
            raise unittest.SkipTest("courage_data.py not found")
        import importlib.util
        spec = importlib.util.spec_from_file_location("courage_data", COURAGE_PY)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    # 1. Citation mechanically verified (occurrence check passed).
    def test_verified_occurs_but_semantic_unverified(self):
        paired = self.mod._citation_status_paired
        sens = self.mod._citation_status_sensitivity
        res = {"citation_verified": True,
               "evidence_snippet": "a quoted passage that occurs in the source"}
        self.assertEqual(paired(res, True), "CITATION_OCCURS_SEMANTIC_UNVERIFIED")
        self.assertEqual(sens(res), "CITATION_OCCURS_SEMANTIC_UNVERIFIED")

    # 2. Citation not offered (no quotation for the check to run on).
    def test_citation_not_offered(self):
        paired = self.mod._citation_status_paired
        sens = self.mod._citation_status_sensitivity
        self.assertEqual(paired({"citation_verified": False}, True), "NO_CITATION")
        self.assertEqual(sens({"citation_verified": False}), "NO_CITATION")
        # An empty snippet is "not offered": the check had nothing to match.
        # (The helper keys on a non-empty snippet, not a non-blank one; a
        # whitespace-only snippet is treated as "offered but unmatched". That
        # state does not occur in any record, so no published fact relies on it.)
        self.assertEqual(paired({"citation_verified": False,
                                 "evidence_snippet": ""}, True), "NO_CITATION")
        self.assertEqual(sens({"citation_verified": False,
                               "evidence_snippet": ""}), "NO_CITATION")

    # 3. Identity gate rejected before citation checking (paired only).
    def test_gate_rejection_is_not_reached_not_failure(self):
        paired = self.mod._citation_status_paired
        # Gate rejected (valid_output False): the citation check never ran, so
        # the result is NOT_REACHED even with a snippet and citation_verified
        # False present. Guards against conflating a gate rejection with a
        # mechanical citation failure.
        res = {"citation_verified": False,
               "evidence_snippet": "some quoted text",
               "error": "vote_unrecognised"}
        self.assertEqual(paired(res, False), "NOT_REACHED")

    # 4. Citation offered but mechanical matching failed.
    def test_mechanical_fail_when_quoted_but_not_found(self):
        paired = self.mod._citation_status_paired
        sens = self.mod._citation_status_sensitivity
        # A snippet was produced and did not occur in any supplied passage
        # (mirrors official-row-584 dense-v1 and sensitivity row 189 B_minimal,
        # both verified in the raw records).
        res = {"citation_verified": False,
               "evidence_snippet": "a paraphrase that is not present verbatim"}
        self.assertEqual(paired(res, True), "CITATION_MECHANICAL_FAIL")
        self.assertEqual(sens(res), "CITATION_MECHANICAL_FAIL")

    # 5. Citation source unavailable / status unknown -> never a fabricated
    #    "unverifiable" state; falls back to the grounded NO_CITATION state.
    def test_no_unavailable_or_unknown_state_is_invented(self):
        paired = self.mod._citation_status_paired
        sens = self.mod._citation_status_sensitivity
        # Empty result (no citation_verified key, or an explicit None) has no
        # quotation to check: it must fall to the grounded NO_CITATION state,
        # never to CITATION_MECHANICAL_FAIL or an invented CITATION_UNVERIFIABLE.
        for res in ({}, {"citation_verified": None}):
            self.assertEqual(paired(res, True), "NO_CITATION")
            self.assertEqual(sens(res), "NO_CITATION")
        # Every reachable status is one of the defined states and is never one
        # of the two legacy ambiguous strings ("verified"/"not run / ...").
        samples = [{"citation_verified": True}, {"citation_verified": False},
                   {"citation_verified": False, "evidence_snippet": "x"},
                   {}, {"citation_verified": None}]
        for res in samples:
            for status in (paired(res, True), sens(res), paired(res, False)):
                self.assertIn(status, VALID_CITATION_STATUSES)
                self.assertNotIn(status, ("verified", "not run / no quotation"))

    # End-to-end integrity: in the shipped data a gate rejection is rendered as
    # NOT_REACHED, never as a citation pass/fail (same rule, checked on output).
    def test_shipped_gate_rejections_render_not_reached(self):
        if not FACTS.exists():
            self.skipTest("facts.json not generated")
        with FACTS.open(encoding="utf-8") as f:
            data = json.load(f)
        passports = data.get("evidence_passport")
        if passports is None:
            self.skipTest("raw tree absent; passports not regenerated")
        checked = 0
        for p in passports:
            per = p.get("arms") or p.get("conditions") or {}
            for name, e in per.items():
                if e.get("contract_validity") == "rejected / invalid":
                    checked += 1
                    self.assertEqual(
                        e.get("citation_mechanical"), "NOT_REACHED",
                        f"{p['case_id']}/{name}: a gate-rejected output must be "
                        "NOT_REACHED, not a citation pass/fail")
        # The three paired gallery cases each contribute a rejected candidate
        # arm; if none were found the guard silently proves nothing.
        self.assertGreater(checked, 0,
                           "no rejected arms found — guard did not exercise")


if __name__ == "__main__":
    unittest.main()
