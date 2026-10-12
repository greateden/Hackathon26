"""Submission contracts; HTTP and encoder doubles are not model measurements."""
import json
import io
from contextlib import redirect_stdout
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import booklet_app as app


def booklet(lang="de", tail="LAST PAGE SENTINEL"):
    return {"source": "only-this.pdf", "sha256": "test-pdf", "language": lang,
            "pages": [{"page": 1, "text": "A" * 4000}, {"page": 2, "text": tail}]}


class ApplicationTests(unittest.TestCase):
    @staticmethod
    def measured(label="entailment", snippet="Verbatim support"):
        return {"label": label, "label_code": app.label_to_code(label),
                "evidence_snippet": snippet, "input_tokens": 41,
                "usage": {"prompt_tokens": 41, "completion_tokens": 7},
                "inference_s": 0.125}

    def test_official_beginner_input_and_exact_output(self):
        judge = Mock()
        judge.judge.return_value = self.measured()
        request = {"id": "case-0043",
                   "reference": {"text": "Verbatim support from the supplied reference."},
                   "claim": {"text": "Example claim"}}
        result = app.classify(request, judge)
        output = app.submission_output(result)
        self.assertEqual(output, {
            "id": "case-0043", "label": 0, "label_name": "entailment",
            "evidence": [{"page": None, "text": "Verbatim support"}],
            "metrics": {"input_tokens": 41, "output_tokens": 7,
                        "inference_time_ms": 125}})
        judge.judge.assert_called_once_with(
            "Example claim", "Verbatim support from the supplied reference.", seed=20261011)

    def test_official_advanced_input_page_provenance_and_nine_language_pairs(self):
        claims = {"de": "Beispielbehauptung", "fr": "Exemple d'affirmation",
                  "it": "Esempio di affermazione"}
        for document_language in app.LANGUAGES:
            for claim_language in app.LANGUAGES:
                judge = Mock()
                judge.judge.return_value = self.measured(snippet="Verbatim support")
                document = {"source": "only-this.pdf", "sha256": "test-pdf",
                            "language": document_language,
                            "pages": [{"page": 7, "text": "Verbatim support on page seven."}]}
                retriever = Mock()
                retriever.retrieve.return_value = [
                    {"page": 7, "text": "Verbatim support on page seven.",
                     "source": "only-this.pdf", "pdf_sha256": "test-pdf"}]
                request = {"id": "case-0042", "vote": "Example vote",
                           "booklet": {"path": "only-this.pdf"},
                           "claim": {"text": claims[claim_language]}}
                output = app.submission_output(
                    app.classify(request, judge, retriever=retriever, booklet=document))
                self.assertEqual(output["id"], "case-0042")
                self.assertEqual(output["evidence"],
                                 [{"page": 7, "text": "Verbatim support"}])
                self.assertEqual(retriever.retrieve.call_args.args[0], document)

    def test_booklet_language_detection(self):
        self.assertEqual(app.detect_language("Der Bundesrat und die Vorlage sind nicht gleich."), "de")
        self.assertEqual(app.detect_language("Les autorités ne sont pas pour une autre loi."), "fr")
        self.assertEqual(app.detect_language("Gli argomenti sono per una legge che non cambia."), "it")

    def test_official_neutral_has_empty_evidence(self):
        judge = Mock()
        judge.judge.return_value = self.measured("neutral", "")
        result = app.classify({"id": "neutral-case",
                               "reference": {"text": "Unrelated reference."},
                               "claim": {"text": "Example claim"}}, judge)
        self.assertEqual(app.submission_output(result)["evidence"], [])

    def test_official_contract_rejects_ambiguous_input_and_ungrounded_verdict(self):
        with self.assertRaisesRegex(ValueError, "booklet or reference, not both"):
            app.validate_request({"id": "bad", "booklet": {"path": "a.pdf"},
                                  "reference": {"text": "reference"},
                                  "claim": {"text": "claim"}})
        result = dict(self.measured(), case_id="case", citation_verified=False, citations=[])
        with self.assertRaisesRegex(ValueError, "require grounded evidence"):
            app.submission_output(result)
        with self.assertRaisesRegex(ValueError, "vote must be"):
            app.validate_request({"id": "bad", "booklet": {"path": "a.pdf"},
                                  "claim": {"text": "claim"}})

    def test_main_prints_only_official_json(self):
        request = {"id": "case-main", "reference": {"text": "Verbatim support."},
                   "claim": {"text": "Example claim"}}
        judge = Mock()
        judge.judge.return_value = self.measured()
        with tempfile.TemporaryDirectory() as d:
            request_path = Path(d) / "request.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            stdout = io.StringIO()
            with patch.object(sys, "argv", ["booklet_app.py", "--input", str(request_path)]), \
                    patch.object(app, "SubmissionJudge", return_value=judge), redirect_stdout(stdout):
                self.assertEqual(app.main(), 0)
        output = json.loads(stdout.getvalue())
        self.assertEqual(set(output), {"id", "label", "label_name", "evidence", "metrics"})
        self.assertIs(type(output["label"]), int)
        self.assertIs(type(output["metrics"]["input_tokens"]), int)
        self.assertIs(type(output["metrics"]["output_tokens"]), int)
        self.assertIs(type(output["metrics"]["inference_time_ms"]), int)

    def test_full_preserves_end_and_all_nine_language_pairs(self):
        for source in app.LANGUAGES:
            for claim in app.LANGUAGES:
                judge = Mock()
                judge.judge.return_value = {"label": "entailment", "label_code": 0,
                                           "evidence_snippet": "LAST PAGE SENTINEL"}
                result = app.classify({"claim": "test", "claim_language": claim,
                                       "evidence": "full", "booklet": "only-this.pdf",
                                       "booklet_language": source}, judge, booklet=booklet(source))
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
            "model": app.MODEL, "choices": [{"message": {"content": '{"label":"neutral"}'}, "finish_reason": "stop"}],
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
        judge = self.make_judge(completion={"model": app.MODEL, "choices": [{"message": {"content": '{"label":"neutral"}'},
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

    def test_cscs_optional_preflight_uses_standard_v1_completion_path(self):
        session = Mock()
        session.headers = {}
        session.get.return_value.json.return_value = {"data": [{"id": app.CSCS_MODEL}]}
        response = Mock()
        response.json.return_value = {
            "model": app.CSCS_MODEL,
            "choices": [{"message": {"content": '{"label":"neutral"}'},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 40, "completion_tokens": 8, "total_tokens": 48}}
        session.post.return_value = response
        env = {"LLM_NAME": app.CSCS_MODEL,
               "LLM_BASE_URL": "https://api.inference.cscs.ch/v1/",
               "LLM_API_KEY": "test-key", "LLM_TOKEN_PREFLIGHT": "optional",
               "SUBMISSION_MODEL_REQUIRED": "1", "LLM_CONTEXT_TOKENS": "32768"}
        with patch.dict(app.os.environ, env), patch("requests.Session", return_value=session):
            judge = app.SubmissionJudge()
            result = judge.judge("claim", "evidence")
        session.get.assert_called_once_with("https://api.inference.cscs.ch/v1/models", timeout=10)
        self.assertEqual(session.post.call_count, 1)
        args, kwargs = session.post.call_args
        self.assertEqual(args[0], "https://api.inference.cscs.ch/v1/chat/completions")
        self.assertNotIn("chat_template_kwargs", kwargs["json"])
        self.assertNotIn("seed", kwargs["json"])
        self.assertEqual(result["label"], "neutral")
        self.assertEqual(result["input_tokens"], 40)
        self.assertEqual(result["finish_reason"], "stop")



if __name__ == "__main__":
    unittest.main()
