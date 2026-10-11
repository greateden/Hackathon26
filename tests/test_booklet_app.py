"""Submission contracts; HTTP and encoder doubles are not model measurements."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import booklet_app as app
import eval_paired


def booklet(lang="de", tail="LAST PAGE SENTINEL"):
    return {"source": "only-this.pdf", "sha256": "test-pdf", "language": lang,
            "pages": [{"page": 1, "text": "A" * 4000}, {"page": 2, "text": tail}]}


class ApplicationTests(unittest.TestCase):
    def test_full_preserves_end_and_all_nine_language_pairs(self):
        for source in app.LANGUAGES:
            for claim in app.LANGUAGES:
                judge = Mock()
                judge.judge.return_value = {"label": "entailment", "label_code": 0,
                                           "evidence_snippet": "LAST PAGE SENTINEL"}
                result = app.classify({"claim": "test", "claim_language": claim,
                                       "evidence": "full"}, judge, booklet=booklet(source))
                self.assertIn("A" * 4000, judge.judge.call_args.args[1])
                self.assertIn("LAST PAGE SENTINEL", judge.judge.call_args.args[1])
                self.assertEqual(result["citations"][0]["page"], 2)
                self.assertTrue(result["citation_verified"])

    def test_retriever_indexes_only_specified_booklet_and_uses_its_language(self):
        import numpy as np
        import types
        encoder = Mock()
        encoder.encode.side_effect = [np.array([[1., 0.]]), np.array([[1., 0.]])]
        module = types.SimpleNamespace(Retriever=Mock(return_value=encoder),
                                       LANG_TO_ADAPTER={"fr": "fr_CH"},
                                       cosine_sim_matrix=lambda q, d: np.array([1.]))
        doc = booklet("fr")
        doc["pages"] = [{"page": 7, "text": "Only the selected booklet."}]
        with patch.dict(sys.modules, {"retriever": module}):
            result = app.BookletRetriever().retrieve(doc, "Behauptung")
        self.assertEqual(encoder.encode.call_args_list[0].args[0], ["Only the selected booklet."])
        self.assertEqual(encoder.encode.call_args_list[1].kwargs["lang_code"], "fr_CH")
        self.assertEqual(result[0]["source"], "only-this.pdf")
        self.assertEqual(result[0]["page"], 7)

    def test_pdf_validation_and_physical_page_numbers(self):
        with tempfile.TemporaryDirectory() as d:
            pdf = Path(d) / "test.pdf"
            pdf.write_bytes(b"not a PDF")
            with self.assertRaisesRegex(ValueError, "not a PDF"):
                app.load_booklet(str(pdf), "de")
            pdf.write_bytes(b"%PDF-fixture")
            proc = Mock(returncode=0, stdout=b"first\f\fthird\f")
            with patch.object(app.subprocess, "run", return_value=proc):
                result = app.load_booklet(str(pdf), "de")
            self.assertEqual([p["page"] for p in result["pages"]], [1, 3])

    def make_judge(self, count=100, completion=None):
        judge = object.__new__(app.SubmissionJudge)
        judge.model, judge.context, judge.max_tokens = app.MODEL, 1000, 512
        judge.base, judge.session = "http://test", Mock()
        token = Mock()
        token.json.return_value = {"count": count}
        response = Mock()
        response.json.return_value = completion or {
            "choices": [{"message": {"content": '{"label":"neutral"}'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": count, "completion_tokens": 8}}
        judge.session.post.side_effect = [token, response]
        return judge

    def test_context_overflow_never_calls_generation(self):
        judge = self.make_judge(900)
        result = judge.judge("claim", "complete text")
        self.assertEqual(result["error"], "context_limit")
        self.assertIsNone(result["label_code"])
        self.assertEqual(judge.session.post.call_count, 1)

    def test_numeric_label_and_no_silent_server_truncation(self):
        judge = self.make_judge()
        self.assertEqual(judge.judge("claim", "evidence")["label_code"], 1)
        judge = self.make_judge(completion={"choices": [{"message": {"content": '{"label":"neutral"}'},
                                                       "finish_reason": "stop"}],
                                          "usage": {"prompt_tokens": 50}})
        result = judge.judge("claim", "evidence")
        self.assertIsNone(result["label"])
        self.assertEqual(result["error"], "prompt_token_count_mismatch_or_missing_usage")

    def test_auth_model_preflight_and_v1_suffix(self):
        session = Mock()
        session.headers = {}
        session.get.return_value.json.return_value = {"data": [{"id": app.MODEL}]}
        env = {"LLM_NAME": app.MODEL, "LLM_BASE_URL": "https://test/v1", "LLM_API_KEY": "test-key"}
        with patch.dict(app.os.environ, env), patch("requests.Session", return_value=session):
            judge = app.SubmissionJudge()
        self.assertEqual(judge.base, "https://test")
        self.assertEqual(session.headers["Authorization"], "Bearer test-key")
        session.get.assert_called_once_with("https://test/v1/models", timeout=10)
        with patch.dict(app.os.environ, {"LLM_NAME": "old-model"}):
            with self.assertRaisesRegex(ValueError, "Submission requires"):
                app.SubmissionJudge()

    def test_gold_not_forwarded_and_paired_changes_are_payload_only(self):
        row = {"claim": "public claim", "claim_language": "de", "booklet_url": "source.pdf",
               "reference_language": "fr", "reference_string": "SECRET GOLD", "entailment_label": 0}
        judge = Mock()
        judge.judge.return_value = {"label": "entailment", "elapsed_s": 0.1}
        retriever = Mock()
        retriever.retrieve.return_value = [{"page": 1, "text": "retrieved"}]
        with patch.object(eval_paired, "load_booklet", return_value=booklet("fr")):
            results = eval_paired.run_pairs([row], [0], judge, retriever, 42)
        self.assertEqual(len(judge.judge.call_args_list), 2)
        for call in judge.judge.call_args_list:
            self.assertNotIn("SECRET GOLD", str(call))
            self.assertEqual(call.kwargs["seed"], 42)
        self.assertEqual(results["full"][0]["row_index"], results["retrieved"][0]["row_index"])


if __name__ == "__main__":
    unittest.main()
