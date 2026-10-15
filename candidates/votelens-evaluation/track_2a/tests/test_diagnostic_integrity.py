"""Missing or disjoint historical data must not certify equivalence."""
import contextlib
import io
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import diag_evidence_ablation as diagnostic


class DiagnosticIntegrityTests(unittest.TestCase):
    def test_missing_required_runs_fail(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(diagnostic.part_b_recorded({}))

    def test_empty_duplicate_and_different_row_sets_are_rejected(self):
        row = {"index": 1, "pred": "neutral", "usage": {"prompt_tokens": 10}}
        for a, b in (([], []), ([row], [dict(row, index=2)]), ([row, row], [row])):
            with self.subTest(a=a, b=b), self.assertRaisesRegex(ValueError, "non-empty unique matching"):
                diagnostic.compare_runs({"items": a}, {"items": b})

    def test_complete_matching_rows_still_compare(self):
        row = {"index": 1, "pred": "neutral", "usage": {"prompt_tokens": 10}}
        self.assertEqual(diagnostic.compare_runs({"items": [row]}, {"items": [row]}), (1, [], []))
