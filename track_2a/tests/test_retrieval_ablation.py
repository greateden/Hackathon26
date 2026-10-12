"""Focused offline checks for the opt-in three-arm retrieval experiment."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import retrieval_ablation as ablation
from eval_nli import load_rows


class FakeEncoder:
    def encode(self, texts, lang_code=None):
        if len(texts) == 1:
            return np.array([[1.0, 0.0]], dtype=np.float32)
        values = [[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]]
        return np.array(values[:len(texts)], dtype=np.float32)


class RetrievalAblationTests(unittest.TestCase):
    def test_frozen_plan_is_balanced_grouped_and_excludes_known_content(self):
        rows = load_rows(ablation.DEFAULT_DATA)
        plan = json.loads(ablation.PLAN.read_text())
        indices = ablation.validate_plan(plan, rows, ablation.DEFAULT_DATA)
        self.assertEqual(len(indices), 81)
        self.assertEqual(len(set(indices)), 81)

    def test_candidate_fusion_preserves_booklet_provenance(self):
        booklet = {"source": "https://example.test/booklet.pdf", "sha256": "pdf",
                   "language": "de", "pages": [
                       {"page": 1, "text": "semantic passage"},
                       {"page": 2, "text": "rareterm lexical passage"},
                       {"page": 3, "text": "unrelated passage"}]}
        retriever = ablation.ExperimentalRetriever(FakeEncoder())
        ranked = retriever.rankings(booklet, "rareterm", "Testvorlage")
        self.assertEqual(ranked[ablation.ARMS[0]][0]["page"], 1)
        self.assertIn(2, [record["page"] for record in ranked[ablation.ARMS[1]][:3]])
        for arm in ablation.ARMS:
            for record in ranked[arm]:
                self.assertEqual(record["source"], booklet["source"])
                self.assertEqual(record["pdf_sha256"], booklet["sha256"])

    def test_proposition_reranking_is_label_agnostic_and_explainable(self):
        claim = "Der Bundesrat gab nicht 80 Milliarden Franken aus, falls das Gesetz scheitert."
        matching = {"text": "Falls das Gesetz scheitert, gab der Bundesrat nicht 80 Milliarden Franken aus."}
        distractor = {"text": "Das Referendumskomitee empfiehlt die Vorlage ohne Zahlen."}
        good = ablation.proposition_features(claim, matching, "Gesetz")
        bad = ablation.proposition_features(claim, distractor, "Gesetz")
        self.assertGreater(ablation.feature_score(good), ablation.feature_score(bad))
        self.assertTrue(good["actor_match"])
        self.assertEqual(good["quantity_coverage"], 1.0)
        self.assertNotIn("label", good)

    def test_sufficiency_diagnostics_do_not_change_a_label(self):
        selected = [{"id": "p1", "page": 1, "source": "booklet", "pdf_sha256": "x",
                     "text": "Der Bundesrat unterstützt die Vorlage."},
                    {"id": "p2", "page": 2, "source": "booklet", "pdf_sha256": "x",
                     "text": "Falls sie angenommen wird, tritt sie 2030 in Kraft."}]
        result = ablation.sufficiency_diagnostics(
            "Der Bundesrat unterstützt die Vorlage unter der Bedingung, dass sie 2030 beginnt.", selected)
        self.assertTrue(result["indicator_only_not_probability"])
        self.assertEqual(result["passage_count"], 2)
        self.assertNotIn("label", result)
        self.assertEqual(len(result["provenance"]), 2)

    def test_reference_matching_distinguishes_exact_and_approximate(self):
        records = [{"id": "a", "text": "alpha beta gamma delta"},
                   {"id": "b", "text": "other material"}]
        ids, method = ablation.locate_reference("alpha beta gamma delta", records)
        self.assertEqual(ids, ["a"])
        self.assertEqual(method, "exact_full_reference")
        ids, method = ablation.locate_reference("not present anywhere", records)
        self.assertEqual(ids, [])
        self.assertEqual(method, "not_located")

    def test_dry_run_outputs_make_zero_inference_claim(self):
        prepared = {"contract": {"items": [], "configuration": {}}, "planned_calls": 243}
        audit = {"schema": ablation.SCHEMA, "n": 81, "rows": []}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            ablation.write_dry_run(path, prepared, audit)
            manifest = json.loads((path / "manifest.json").read_text())
            summary = json.loads((path / "summary.json").read_text())
            self.assertEqual(manifest["inference_calls"], 0)
            self.assertEqual(summary["inference_calls"], 0)
            for name in ("manifest.json", "predictions.jsonl", "summary.json",
                         "paired_comparison.csv", "error_analysis.md"):
                self.assertTrue((path / name).is_file())

    def test_experimental_summary_reads_nested_token_usage(self):
        item = {"row_index": 1, "pair": "de->fr", "gold": "neutral"}
        records = []
        for arm in ablation.ARMS:
            records.append({"key": "1:" + arm, "arm": arm, "pair": "de->fr",
                            "gold": "neutral", "pred": "neutral", "correct": True,
                            "status": "completed", "elapsed_s": 1.0,
                            "result": {"error": None, "retrieval_s": 0.1,
                                       "citation_verified": True,
                                       "usage": {"prompt_tokens": 12, "completion_tokens": 3}}})
        manifest = {"contract": {"items": [item]}}
        with tempfile.TemporaryDirectory() as directory:
            summary = ablation.render_outputs(Path(directory), manifest, records, "COMPLETE")
        for arm in ablation.ARMS:
            self.assertEqual(summary["methods"][arm]["prompt_tokens_total"], 12)


if __name__ == "__main__":
    unittest.main()
