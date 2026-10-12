"""Offline runner contracts. Model replies and deployment commands are doubles."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import booklet_app as app
import experiment_runner as runner
import serve_experiments as serving

FIXTURE = json.loads((Path(__file__).parent / "fixtures/paired_examples.json").read_text())


def completion(label="neutral", **changes):
    result = {"model": app.MLX_MODEL, "choices": [{"message": {"content": json.dumps(
        {"label": label, "evidence_snippet": "Evidence"})}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 8}}
    result.update(changes)
    return result


def judge_with(reply=None):
    judge = object.__new__(app.SubmissionJudge)
    judge.model, judge.context, judge.max_tokens = app.MLX_MODEL, 32768, 512
    judge.base, judge.session = "http://test", Mock()
    token, response = Mock(), Mock()
    token.json.return_value = {"count": 10}
    response.json.return_value = reply if reply is not None else completion()
    judge.session.post.side_effect = [token, response]
    return judge


class JudgeContracts(unittest.TestCase):
    def test_citation_soft_hyphen_preserves_strict_provenance(self):
        request = {"claim": "test", "booklet": "a.pdf", "claim_language": "it",
                   "booklet_language": "it", "evidence": "full"}
        booklet = {"source": "a.pdf", "sha256": "s", "language": "it",
                   "pages": [{"page": 15, "text": "Più abita\u00ad\nzioni a prezzi accessibili."}]}
        judge = Mock()
        for snippet, verified in (("Più abitazioni a prezzi accessibili.", True),
                                  ("Più abitazioni non a prezzi accessibili.", False),
                                  ("Più abitazioni ... accessibili.", False)):
            judge.judge.return_value = {"label": "neutral", "evidence_snippet": snippet}
            result = app.classify(request, judge, booklet=booklet)
            self.assertEqual(result["citation_verified"], verified)
            self.assertEqual(result["label"], "neutral")
        for text in ("abita-\nzioni", "abita zioni", "abita\nzioni"):
            self.assertNotEqual(app.normalise_citation(text), "abitazioni")
        # A quotation from an unselected chunk remains unverified.
        retriever = Mock()
        retriever.retrieve.return_value = [{"page": 15, "text": "zioni a prezzi accessibili.",
                                          "source": "a.pdf", "pdf_sha256": "s"}]
        judge.judge.return_value = {"label": "neutral", "evidence_snippet": "Più abitazioni a prezzi accessibili."}
        self.assertFalse(app.classify(dict(request, evidence="retrieved"), judge, retriever, booklet)["citation_verified"])

    def test_bad_models_response_and_config(self):
        for model in ("Apertus-v1.50", "fake/Apertus-v1.5-70B", "swiss-ai/Apertus-v1.1-8B"):
            self.assertFalse(app.is_apertus_v15(model))
        for model in ("wrong", None):
            result = judge_with(completion(model=model)).judge("claim", "Evidence")
            self.assertEqual(result["error"], "response_model_mismatch_or_missing")
            self.assertIsNone(result["label"])
        with patch.dict(os.environ, {"SUBMISSION_MODEL_REQUIRED": "1", "LLM_NAME": app.MLX_MODEL}):
            with self.assertRaisesRegex(ValueError, "Docker submission"):
                app.SubmissionJudge()

    def test_usage_malformed_and_incomplete_responses(self):
        for reply in (completion(usage={}), completion(usage={"prompt_tokens": True, "completion_tokens": 3}),
                      completion(usage={"prompt_tokens": 10}), {"model": app.MLX_MODEL, "choices": []}):
            result = judge_with(reply).judge("claim", "Evidence")
            self.assertIsNone(result["label"])
            self.assertTrue(result.get("error"))
        for text in ("nonsense", '{"label":"neutral-ish"}'):
            reply = completion()
            reply["choices"][0]["message"]["content"] = text
            self.assertIsNone(judge_with(reply).judge("claim", "Evidence")["label"])
        reply = completion()
        reply["choices"][0]["finish_reason"] = "length"
        self.assertEqual(judge_with(reply).judge("claim", "Evidence")["error"], "incomplete_completion")

    def test_timeout_and_endpoint_down(self):
        import requests
        judge = judge_with()
        judge.session.post.side_effect = requests.Timeout("private detail")
        result = judge.judge("claim", "Evidence")
        self.assertEqual(result["error"], "endpoint_or_tokenisation_error:Timeout")
        self.assertNotIn("private detail", json.dumps(result))
        session = Mock()
        session.get.side_effect = requests.ConnectionError()
        with patch("requests.Session", return_value=session), patch.dict(os.environ, {
                "LLM_NAME": app.MLX_MODEL, "LLM_BASE_URL": "http://test", "SUBMISSION_MODEL_REQUIRED": "0"}):
            with self.assertRaisesRegex(RuntimeError, "preflight failed"):
                app.SubmissionJudge()

    def test_model_text_cannot_overwrite_measured_provenance(self):
        reply = completion()
        reply["choices"][0]["message"]["content"] = json.dumps(
            {"label": "neutral", "model": "fake", "usage": {"prompt_tokens": 999}, "input_tokens": 999})
        result = judge_with(reply).judge("claim", "Evidence")
        self.assertEqual(result["model"], app.MLX_MODEL)
        self.assertEqual(result["input_tokens"], 10)
        self.assertEqual(result["usage"]["prompt_tokens"], 10)

    def test_invalid_inputs_fail_before_endpoint(self):
        for request in (None, [], {}, {"claim": "valid"}, {"claim": "valid", "booklet": ["two"]}):
            with self.assertRaises(ValueError):
                app.validate_request(request)
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "request.json"
            file.write_text('{}')
            with patch.object(sys, "argv", ["booklet_app.py", "--input", str(file)]), patch.object(app, "SubmissionJudge") as model:
                self.assertEqual(app.main(), 1)
                model.assert_not_called()

    def test_all_nine_verified_pairs_and_no_unrelated_evidence(self):
        pairs = set()
        for example in FIXTURE["examples"]:
            row = example["row"]
            request = {"claim": row["claim"], "claim_language": row["claim_language"],
                       "booklet": row["booklet_url"], "booklet_language": row["reference_language"]}
            pairs.add((request["claim_language"], request["booklet_language"]))
            booklet = {"source": request["booklet"], "sha256": "fixture", "language": request["booklet_language"],
                       "pages": [{"page": 1, "text": "Evidence " + "x" * 2500}, {"page": 2, "text": "Last page"}]}
            passage = dict(booklet["pages"][0], source=booklet["source"], pdf_sha256="fixture")
            retriever = Mock()
            retriever.retrieve.return_value = [passage]
            for mode in ("full", "retrieved"):
                judge = Mock()
                judge.judge.return_value = {"label": "neutral", "evidence_snippet": "Evidence"}
                result = app.classify(dict(request, evidence=mode), judge, retriever, booklet)
                self.assertTrue(result["citation_verified"])
                self.assertNotIn(row["reference_string"], judge.judge.call_args.args[1])
                if mode == "full":
                    self.assertIn("Last page", judge.judge.call_args.args[1])
                self.assertEqual(result["booklet"], row["booklet_url"])
            retriever.retrieve.return_value = [dict(passage, source="unrelated.pdf")]
            with self.assertRaisesRegex(ValueError, "selected booklet"):
                app.classify(request, Mock(), retriever, booklet)
        self.assertEqual(len(pairs), 9)

    def test_bad_snippet_not_verified_and_mismatched_booklet_rejected(self):
        request = {"claim": "test", "booklet": "a.pdf", "claim_language": "de", "booklet_language": "de", "evidence": "full"}
        booklet = {"source": "a.pdf", "sha256": "s", "language": "de", "pages": [{"page": 1, "text": "Evidence"}]}
        for snippet in (None, "Not in this PDF"):
            judge = Mock()
            judge.judge.return_value = {"label": "neutral", "evidence_snippet": snippet}
            self.assertFalse(app.classify(request, judge, booklet=booklet)["citation_verified"])
        with self.assertRaisesRegex(ValueError, "does not match"):
            app.classify(dict(request, booklet="b.pdf"), Mock(), booklet=booklet)


class RunnerContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / "data/experiments/test"
        self.patch_root = patch.object(runner, "PROJECT_ROOT", self.root)
        self.patch_root.start()
        self.addCleanup(self.patch_root.stop)
        self.args = runner.parser().parse_args(["run", "--out", str(self.directory), "--retries", "0"])
        row = FIXTURE["examples"][0]["row"]
        self.request = {"claim": row["claim"], "claim_language": row["claim_language"],
                        "booklet": row["booklet_url"], "booklet_language": row["reference_language"]}
        item = {"row_index": 1095, "request": self.request, "gold": runner.CODE_TO_LABEL[row["entailment_label"]],
                "reference": row["reference_string"]}
        self.booklet = {"source": row["booklet_url"], "language": row["reference_language"], "sha256": "test",
                        "pages": [{"page": 1, "text": "Evidence"}]}
        info = {"config_sha256": "a", "shards": [], "mlx_lm_version": "0.32.0", "quantisation": {"bits": 6}}
        self.prepared = {"contract": {"items": [item], "model_cache": info}, "git_dirty": True,
                         "encoder_path": Path("cache"), "booklets": {(row["booklet_url"], row["reference_language"]): self.booklet}}
        self.metadata = dict(info, instance_id="server-test")
        passage = dict(self.booklet["pages"][0], source=row["booklet_url"], pdf_sha256="test")
        self.reply = {"label": item["gold"], "label_code": row["entailment_label"], "elapsed_s": 0.1,
                      "inference_s": 0.05, "retrieval_s": 0.02, "passages": [passage],
                      "citations": [passage], "citation_verified": True, "pdf_sha256": "test",
                      "finish_reason": "stop",
                      "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
                      "prompt_sha256": "hash"}

    def execute(self, side_effect=None):
        with patch.object(runner, "connect", return_value=(Mock(), self.metadata)), \
             patch.object(runner, "make_retriever", return_value=Mock()), \
             patch.object(runner, "classify", return_value=self.reply, side_effect=side_effect) as classify:
            result = runner.execute(self.args, self.prepared)
            return result, classify

    def test_immediate_results_schema_and_resume_without_calls(self):
        calls = []
        def predict(*args, **kwargs):
            self.assertEqual(len(runner.read_log(self.directory / "predictions.jsonl")), len(calls))
            calls.append(True)
            return self.reply
        code, model = self.execute(predict)
        self.assertEqual(code, 0)
        self.assertEqual(model.call_count, 2)
        records = runner.read_log(self.directory / "predictions.jsonl")
        for record in records:
            self.assertEqual(record["schema"], runner.SCHEMA)
            self.assertIn("messages", record)
            self.assertNotIn(self.prepared["contract"]["items"][0]["reference"], str(record["messages"]))
        self.args.resume = True
        with patch.object(runner, "connect", side_effect=AssertionError("must not reconnect")):
            self.assertEqual(runner.execute(self.args, self.prepared), 0)
        for name in ("manifest.json", "predictions.jsonl", "summary.json", "summary.md"):
            self.assertTrue((self.directory / name).is_file())

    def test_nested_usage_in_both_summary_tables(self):
        self.reply["retrieval_s"] = 0.25
        self.execute()
        summary = json.loads((self.directory / "summary.json").read_text())
        for table in ("methods", "paired_success_only"):
            for mode in ("full", "retrieved"):
                stats = summary[table][mode]
                self.assertEqual(stats["prompt_tokens_total"], 10)
                self.assertEqual(stats["completion_tokens_total"], 8)
                self.assertEqual(stats["prompt_tokens"],
                                 {"measured_total": 10, "measured_rows": 1, "missing_rows": 0})
                self.assertEqual(stats["mean_retrieval_s"], 0.25)

    def test_usage_coverage_excludes_missing_and_preflight_counts(self):
        record = {"gold": "neutral", "pred": None, "correct": False, "elapsed_s": 1,
                  "result": {"input_tokens": 69998, "error": "context_limit"}}
        for usage in (None, {}, {"prompt_tokens": None}, {"prompt_tokens": True},
                      {"prompt_tokens": "10"}, {"prompt_tokens": -1}):
            row = dict(record, result=dict(record["result"], usage=usage))
            stats = runner.summarise_records([row])
            self.assertIsNone(stats["prompt_tokens_total"])
            self.assertEqual(stats["prompt_tokens"],
                             {"measured_total": None, "measured_rows": 0, "missing_rows": 1})
        successful = dict(record, pred="neutral", correct=True,
                          result={"usage": {"prompt_tokens": 10, "completion_tokens": 8}})
        stats = runner.summarise_records([record, successful])
        self.assertEqual(stats["prompt_tokens_total"], 10)
        self.assertEqual(stats["prompt_tokens"]["missing_rows"], 1)
        self.assertEqual(stats["completion_tokens_total"], 8)
        self.assertEqual(stats["accuracy"], 0.5)

    def test_mismatched_resume_refused(self):
        self.execute()
        self.args.resume = True
        self.prepared["contract"]["changed"] = True
        with self.assertRaisesRegex(ValueError, "Resume refused"):
            self.execute()

    def test_interruption_preserved_and_retry_explicit(self):
        self.assertEqual(self.execute([KeyboardInterrupt()])[0], 130)
        self.args.resume = True
        code, model = self.execute()
        self.assertEqual(code, 1)
        self.assertEqual(model.call_count, 1)  # Only the never-started arm.
        self.args.retry_failed = True
        code, model = self.execute()
        self.assertEqual(code, 0)
        self.assertEqual(model.call_count, 1)
        self.assertEqual(len(runner.read_log(self.directory / "predictions.jsonl")), 3)

    def test_orphan_start_is_retained_as_unknown_outcome(self):
        self.execute()
        records = runner.read_log(self.directory / "predictions.jsonl")
        (self.directory / "predictions.jsonl").write_text(json.dumps(records[0]) + "\n")
        self.args.resume = True
        code, model = self.execute()
        self.assertEqual(code, 1)
        model.assert_not_called()
        last = runner.read_log(self.directory / "predictions.jsonl")[-1]
        self.assertEqual(last["result"]["error"], "interrupted_outcome_unknown")

    def test_transient_retry_keeps_original_failure(self):
        self.args.retries = 1
        fail = dict(self.reply, label=None, error="endpoint_or_tokenisation_error:Timeout")
        with patch.object(runner.time, "sleep"):
            code, model = self.execute([fail, self.reply, self.reply])
        self.assertEqual(code, 0)
        self.assertEqual(model.call_count, 3)
        summary = json.loads((self.directory / "summary.json").read_text())
        self.assertEqual(summary["failed_attempts"], 1)
        self.assertEqual(summary["completed"], 2)

    def test_error_with_label_not_counted_as_correct(self):
        failure = dict(self.reply, error="context_limit")
        self.assertEqual(self.execute([failure, failure])[0], 1)
        summary = json.loads((self.directory / "summary.json").read_text())
        self.assertEqual(summary["methods"]["full"]["accuracy"], 0)
        self.assertEqual(summary["paired_success_only"]["full"]["n"], 0)

    def test_blocked_endpoint_writes_four_artifacts(self):
        with patch.object(runner, "connect", side_effect=ConnectionError):
            self.assertEqual(runner.execute(self.args, self.prepared), 2)
        self.assertTrue((self.directory / "summary.json").exists())
        self.assertTrue((self.directory / "predictions.jsonl").exists())
        self.assertEqual(json.loads((self.directory / "summary.json").read_text())["completed"], 0)

    def test_truncated_tail_recovered_without_losing_original(self):
        self.directory.mkdir(parents=True)
        path = self.directory / "predictions.jsonl"
        path.write_bytes(b'{"ok":1}\n{"broken":')
        self.assertEqual(runner.read_log(path), [{"ok": 1}])
        self.assertEqual(len(list(self.directory.glob("*.partial-*"))), 1)
        path.write_bytes(b'bad\n{"ok":1}\n')
        with self.assertRaisesRegex(ValueError, "Corrupt"):
            runner.read_log(path)

    def test_preflight_mode_does_not_connect(self):
        prepared = dict(self.prepared, issues=[], submission_static_issues=[], status="PASS", planned_calls=2, max_calls_with_retries=2)
        with patch.object(runner, "prepare", return_value=prepared), patch.object(runner, "connect") as connect:
            self.assertEqual(runner.main(["preflight", "--out", str(self.directory)]), 0)
            connect.assert_not_called()
        with patch.object(runner, "prepare", side_effect=FileNotFoundError), patch.object(runner, "connect") as connect:
            self.assertEqual(runner.main(["preflight", "--out", str(self.directory)]), 2)
            connect.assert_not_called()

    def test_cli_options_and_output_validation(self):
        with self.assertRaises(SystemExit):
            runner.main(["run", "--retries", "-1"])
        with self.assertRaises(SystemExit):
            runner.main(["run", "--retry-failed"])
        with self.assertRaises(SystemExit):
            runner.main(["submission-smoke"])
        with self.assertRaises(SystemExit):
            runner.main(["run", "--dry-run"])
        with self.assertRaises(ValueError):
            runner.output_path(self.root / "outside")
        with self.assertRaises(ValueError):
            runner.endpoint("https://user:password@example.com")

    def smoke(self, configuration=None, outcome=None, docker=True, deployment="external", gpu=True,
              dry_run=False):
        for name in ("Dockerfile", "Makefile", "compose.submission.yaml", "compose.managed.yaml"):
            (self.root / name).write_text("fixture")
        self.args.deployment = deployment
        self.args.live = not dry_run
        self.args.dry_run = dry_run
        self.args.request = self.root / "request.json"
        self.args.request.write_text(json.dumps(self.request))
        config = configuration or {"services": {"app": {"environment": {
            "LLM_NAME": app.MODEL, "LLM_BASE_URL": "http://test", "LLM_API_KEY": "secret-value",
            "LLM_CONTEXT_TOKENS": "32768", "LLM_TOKEN_PREFLIGHT": "required"}}}}
        if deployment == "managed":
            config["services"]["apertus"] = {"environment": {"HF_TOKEN": ""}}
        self.smoke_commands = []
        def run(argv, **kwargs):
            self.smoke_commands.append(argv)
            if argv[:2] == ["docker", "info"]:
                return SimpleNamespace(returncode=0 if docker else 1, stdout='{"nvidia":{}}' if gpu else "{}")
            if "config" in argv:
                return SimpleNamespace(returncode=0, stdout=json.dumps(config))
            if argv[:2] in (["make", "run"], ["make", "run-cscs"]):
                if isinstance(outcome, Exception):
                    raise outcome
                if outcome:
                    runner.write_json(self.directory / "result.json", outcome)
                return SimpleNamespace(returncode=0, stdout="secret-value")
            return SimpleNamespace(returncode=0, stdout="git-fixture")
        env = {"CSCS_INFERENCE_API_KEY": "secret-value"} if deployment == "cscs" else {}
        with patch.object(runner.shutil, "which", return_value="available"), \
             patch.object(runner, "command", side_effect=run), patch.dict(os.environ, env):
            return runner.smoke(self.args)

    def test_smoke_missing_daemon_is_blocked(self):
        self.assertEqual(self.smoke(docker=False), 2)
        self.assertFalse(json.loads((self.directory / "summary.json").read_text())["docker_inference"])

    def test_smoke_missing_gpu_is_blocked(self):
        self.assertEqual(self.smoke(deployment="managed", gpu=False), 2)
        self.assertIn("NVIDIA", json.loads((self.directory / "summary.json").read_text())["reason"])

    def test_smoke_missing_credentials_is_blocked(self):
        self.assertEqual(self.smoke(deployment="managed"), 2)
        self.assertIn("HF_TOKEN", json.loads((self.directory / "summary.json").read_text())["reason"])

    def test_smoke_real_result_required_and_secrets_omitted(self):
        self.assertEqual(self.smoke(), 1)
        self.assertNotIn("secret-value", "".join(p.read_text() for p in self.directory.glob("*.json*")))

    def test_smoke_success_double_is_not_static_success(self):
        result = dict(self.reply, **self.request, model=app.MODEL, response_model=app.MODEL)
        self.assertEqual(self.smoke(outcome=result), 0)
        record = json.loads((self.directory / "verification.json").read_text())
        self.assertEqual(record["status"], "PASS")
        self.assertEqual(record["docker"]["process_exit_code"], 0)
        self.assertEqual(record["inference"]["calls"], 1)
        self.assertTrue(all(record["acceptance_criteria"].values()))
        self.assertEqual(record["prediction"]["correctness"], "not_assessed")

    def test_smoke_dry_run_makes_no_endpoint_or_inference_call(self):
        self.assertEqual(self.smoke(dry_run=True), 0)
        record = json.loads((self.directory / "verification.json").read_text())
        self.assertEqual(record["status"], "READY")
        self.assertEqual(record["inference"]["calls"], 0)
        self.assertFalse(record["docker_inference"])
        self.assertFalse(any(command[:2] in (["make", "run"], ["make", "run-cscs"])
                             for command in self.smoke_commands))

    def test_smoke_rejects_incomplete_or_invalid_usage(self):
        result = dict(self.reply, **self.request, model=app.MODEL, response_model=app.MODEL,
                      finish_reason="length", usage={"prompt_tokens": 10, "completion_tokens": 8})
        self.assertEqual(self.smoke(outcome=result), 1)
        failed = json.loads((self.directory / "verification.json").read_text())["failed_acceptance_criteria"]
        self.assertIn("finish_reason_stop", failed)
        self.assertIn("valid_token_usage", failed)

    def test_cscs_external_smoke_accepts_70b_and_optional_preflight(self):
        config = {"services": {"app": {"environment": {
            "LLM_NAME": app.CSCS_MODEL, "LLM_BASE_URL": "https://api.inference.cscs.ch/v1",
            "LLM_API_KEY": "secret-value", "LLM_CONTEXT_TOKENS": "32768",
            "LLM_TOKEN_PREFLIGHT": "optional"}}}}
        result = dict(self.reply, **self.request, model=app.CSCS_MODEL,
                      response_model=app.CSCS_MODEL)
        self.assertEqual(self.smoke(configuration=config, outcome=result, deployment="cscs"), 0)
        manifest = json.loads((self.directory / "manifest.json").read_text())
        self.assertEqual(manifest["model"], app.CSCS_MODEL)
        self.assertEqual(manifest["configuration"]["LLM_TOKEN_PREFLIGHT"], "optional")

    def test_smoke_timeout(self):
        import subprocess
        self.assertEqual(self.smoke(outcome=subprocess.TimeoutExpired("make", 1)), 1)


class ServerAdapterContracts(unittest.TestCase):
    def test_loader_provenance_and_exact_server_tokenisation(self):
        class Provider:
            def _load(self, *args):
                self.model = SimpleNamespace()
        class Handler:
            def do_GET(self):
                raise AssertionError("Unexpected native GET")
            def do_POST(self):
                return "native completion"
        server = SimpleNamespace(ModelProvider=Provider, APIHandler=Handler)
        metadata = {"model": app.MLX_MODEL, "revision": serving.REVISION}
        serving.install_adapter(server, Path("cached-snapshot"), metadata, 32768)
        provider = Provider()
        provider._load(app.MLX_MODEL)
        with self.assertRaises(ValueError):
            provider._load("wrong")
        handler = Handler()
        handler._set_completion_headers = Mock()
        handler.end_headers = Mock()
        handler.wfile = io.BytesIO()
        handler.path = "/experiment-metadata"
        handler.do_GET()
        self.assertTrue(json.loads(handler.wfile.getvalue())["loaded"])
        payload = json.dumps({"model": app.MLX_MODEL, "messages": [{"role": "user", "content": "test"}]}).encode()
        handler.path = "/tokenize"
        handler.rfile = io.BytesIO(payload)
        handler.wfile = io.BytesIO()
        handler.headers = {"Content-Length": str(len(payload))}
        handler.response_generator = SimpleNamespace(model_provider=SimpleNamespace(tokenizer="same-tokenizer"),
                                                       _tokenize=Mock(return_value=([1, 2, 3], [], [], "normal")))
        handler.do_POST()
        self.assertEqual(json.loads(handler.wfile.getvalue())["count"], 3)
        self.assertEqual(handler.response_generator._tokenize.call_args.args[0], "same-tokenizer")


if __name__ == "__main__":
    unittest.main()
