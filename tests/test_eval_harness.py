"""Offline checks of the eval-harness accounting and dataset-sampling path.

Three invariants, all of them about numbers staying readable as what they
measure:

  * a judgement that produced no label is recorded as an error (pred=None),
    never as a class, and never defaulted to neutral;
  * error items stay inside the latency accounting (`*_all` keys), so a run
    whose failures were slow (endpoint timeouts) cannot read as a fast one;
  * `--sampler prefix` reproduces the recorded dev selection, while
    `--sampler balanced` gives a class-stratified slice. The dataset starts
    with a block of entailment rows, so a prefix slice measures nothing.

Everything runs on scripted judges and synthetic fixtures: no model, no
server, no network. Run from the repo root:
  PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import eval_nli
import sampling
from nli_judge import parse_nli_response


def item(code, claim="the claim", ref="a piece of evidence", lang="de"):
    return {"claim": claim, "entailment_label": code,
            "reference_string": ref, "reference_language": lang,
            "claim_language": "en"}


class ScriptedJudge:
    """Same judge() signature as the real backends, answers from a script.

    A dict answer is passed through as-is (that is how an endpoint error
    arrives); a string answer goes through the real parser, so a reasoning
    reply reaches the harness the way a model's would.
    """

    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []

    def judge(self, claim, passages):
        assert len(self.seen) < len(self.replies), "script ran out of replies"
        reply = self.replies[len(self.seen)]
        self.seen.append(claim)
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, dict):
            return reply
        # A real backend hands the harness the parser's verdict *dict*
        # (MlxJudge/OllamaJudge/OpenAICompatJudge all return
        # parse_nli_response(raw)), and eval_nli.evaluate reads
        # verdict["label"], which must be a label name or None. So the parsed
        # dict is passed through as-is; only the bookkeeping key is added.
        verdict = dict(parse_nli_response(reply))
        verdict["usage"] = {"prompt_tokens": 10, "completion_tokens": 1}
        return verdict


EVIDENCE = [{"id": "gold", "lang": "de", "year": "?",
             "source_file": "fixture", "score": 1.0, "text": "some evidence"}]


class EvaluateAccountingTests(unittest.TestCase):
    """evaluate(): what a row looks like when the chain broke."""

    def run_case(self, items, replies):
        judge = ScriptedJudge(replies)
        with contextlib.redirect_stdout(io.StringIO()):
            results = eval_nli.evaluate(items, judge,
                                        evidence_for=lambda it: EVIDENCE)
        return results, judge

    def test_unparseable_reply_is_an_error_not_a_label(self):
        items = [item(0), item(1), item(2)]
        replies = ["entailment",
                   "Let me think. This looks like a contradiction to me.",
                   "contradiction"]
        results, judge = self.run_case(items, replies)
        self.assertEqual([r["pred"] for r in results],
                         ["entailment", None, "contradiction"])
        # a reasoning reply must not be keyword-scanned, and must not
        # silently default to neutral either
        self.assertNotIn(results[1]["pred"], eval_nli.CLASSES)
        self.assertIsNone(results[1]["pred_code"])
        self.assertFalse(results[1]["correct"])
        self.assertEqual(results[1]["error"], "unparseable_response")
        self.assertEqual(len(judge.seen), 3)

        summary = eval_nli.summarise(results)
        self.assertEqual(summary["n"], 3)
        self.assertEqual(summary["errors"], 1)
        self.assertEqual(summary["error_kinds"], {"unparseable_response": 1})
        self.assertEqual(summary["confusion"]["neutral"]["ERROR"], 1)
        self.assertEqual(summary["confusion"]["neutral"]["neutral"], 0)
        self.assertEqual(summary["accuracy"], round(2 / 3, 3))
        self.assertEqual(summary["completion_tokens_total"], 3)

    def test_missing_evidence_never_reaches_the_judge(self):
        judge = ScriptedJudge(["entailment"])
        with contextlib.redirect_stdout(io.StringIO()):
            results = eval_nli.evaluate([item(0)], judge,
                                        evidence_for=lambda it: [])
        self.assertIsNone(results[0]["pred"])
        self.assertTrue(results[0]["no_evidence"])
        self.assertEqual(results[0]["error"], "no evidence passages retrieved")
        self.assertEqual(judge.seen, [])  # the chain broke before the judge
        self.assertEqual(eval_nli.summarise(results)["error_kinds"],
                         {"retrieval_error": 1})

    def test_judge_exception_becomes_a_counted_error(self):
        judge = ScriptedJudge([ConnectionError("endpoint is down")])
        with contextlib.redirect_stdout(io.StringIO()):
            results = eval_nli.evaluate([item(2)], judge,
                                        evidence_for=lambda it: EVIDENCE)
        self.assertIsNone(results[0]["pred"])
        self.assertIn("judge raised", results[0]["error"])
        summary = eval_nli.summarise(results)
        self.assertEqual(summary["errors"], 1)
        self.assertEqual(summary["error_kinds"], {"endpoint_error": 1})


class LatencyAccountingTests(unittest.TestCase):
    """The two latency bases: successes only, and every item."""

    def test_error_cost_stays_visible(self):
        rows = [
            {"gold": "entailment", "pred": "entailment", "correct": True,
             "elapsed_s": 1.0, "error": None},
            {"gold": "neutral", "pred": None, "correct": False,
             "elapsed_s": 120.0, "error": "Endpoint error: timed out"},
        ]
        summary = eval_nli.summarise(rows)
        self.assertEqual(summary["mean_latency_s"], 1.0)
        self.assertEqual(summary["mean_latency_s_all"], 60.5)
        self.assertEqual(summary["errors"], 1)

    def test_all_error_run_reports_no_success_latency_but_still_times(self):
        rows = [{"gold": "neutral", "pred": None, "correct": False,
                 "elapsed_s": 9.0, "error": "unparseable_response"}]
        summary = eval_nli.summarise(rows)
        self.assertIsNone(summary["mean_latency_s"])
        self.assertEqual(summary["mean_latency_s_all"], 9.0)
        self.assertEqual(summary["median_latency_s_all"], 9.0)

    def test_empty_run(self):
        summary = eval_nli.summarise([])
        self.assertEqual(summary["n"], 0)
        self.assertIsNone(summary["mean_latency_s"])
        self.assertIsNone(summary["mean_latency_s_all"])


class SamplerTests(unittest.TestCase):
    """balanced_sample: deterministic, class-stratified, order-preserving."""

    def test_prefills_a_short_list_with_every_class(self):
        items = [item(0, "e1"), item(0, "e2"), item(0, "e3"),
                 item(1, "n1"), item(1, "n2"), item(2, "c1")]
        chosen = sampling.balanced_sample(items, 3, seed=1)
        self.assertEqual([it["entailment_label"] for it in chosen], [0, 1, 2])

    def test_round_robin_keeps_the_classes_even(self):
        items = [item(0) for _ in range(5)] + [item(1)] * 4 + [item(2)] * 4
        chosen = sampling.balanced_sample(items, 6, seed=7)
        self.assertEqual(len(chosen), 6)
        self.assertEqual(sampling.label_counts(chosen),
                         {"0": 2, "1": 2, "2": 2})

    def test_stable_under_replay_and_no_duplicates(self):
        items = [item(i % 3, f"claim {i}") for i in range(12)]
        first = sampling.balanced_sample(items, 5, seed=3)
        second = sampling.balanced_sample(items, 5, seed=3)
        self.assertEqual([it["claim"] for it in first],
                         [it["claim"] for it in second])
        self.assertEqual(len({id(r) for r in first}), 5)

    def test_oversized_n_never_duplicates_or_invents_items(self):
        items = [item(0), item(1)]
        self.assertEqual(len(sampling.balanced_sample(items, 9, seed=0)), 2)


class SamplerWiringTests(unittest.TestCase):
    """eval_nli.main(): the flag must change WHICH items get scored, and the
    output artefact must not be confusable with a prefix-slice run."""

    FIXTURE = ([item(0, f"e{i}") for i in range(5)]
               + [item(1, f"n{i}") for i in range(2)]
               + [item(2, f"c{i}") for i in range(2)])

    def write_fixture(self, tmp):
        data = Path(tmp) / "fixture.jsonl"
        data.write_text("".join(json.dumps(r) + "\n" for r in self.FIXTURE),
                        encoding="utf-8")
        return data

    def run_main(self, argv, tmp, name="out.json"):
        """Run the CLI end to end on the fixture with the lexical judge.

        `name` is a parameter because main() refuses to overwrite an existing
        artefact (SystemExit, by design): two runs that share one tempdir must
        not share one output path, or the second measures nothing.
        """
        data = self.write_fixture(tmp)
        out = Path(tmp) / name
        argv = ["eval_nli.py", "--data", str(data), "--out", str(out),
                "--backend", "lexical"] + argv
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), patch.object(sys, "argv", argv):
            eval_nli.main()
        with out.open(encoding="utf-8") as fh:
            payload = json.load(fh)
        return payload, buf.getvalue()

    def test_default_prefix_slice_keeps_the_recorded_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload, text = self.run_main(["--limit", "3", "--split", "dev"],
                                          tmp)
            self.assertEqual(payload["meta"]["sampler"], "prefix")
            self.assertEqual(payload["summary"]["n"], 3)
            # the fixture is front-loaded with entailment, exactly like the
            # real set: a prefix slice is single-class and says so out loud
            self.assertEqual(list(payload["meta"]["class_mix"]),
                             ["entailment"])
            self.assertIn("WARNING: selected slice covers 1/3", text)
            self.assertNotIn("_balanced", payload["meta"]["data_file"])

    def test_balanced_sampler_scores_all_three_classes(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload, text = self.run_main(
                ["--limit", "3", "--sampler", "balanced", "--split", "dev"],
                tmp)
            self.assertEqual(payload["meta"]["sampler"], "balanced")
            self.assertEqual(sorted(payload["meta"]["class_mix"].values()),
                             [1, 1, 1])
            # full coverage, so the single-class warning must be silent
            self.assertNotIn("WARNING", text)
            # the header line names the sampler, so a log line identifies the
            # sample it describes
            self.assertIn("(balanced)", text)

    def test_the_two_samplers_score_different_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            balanced, _ = self.run_main(
                ["--limit", "3", "--sampler", "balanced", "--split", "dev"],
                tmp, "out-balanced.json")
            prefix, _ = self.run_main(["--limit", "3", "--split", "dev"],
                                      tmp, "out-prefix.json")
        self.assertNotEqual([i["claim"] for i in balanced["items"]],
                            [i["claim"] for i in prefix["items"]])
        self.assertEqual(len(balanced["items"]), len(prefix["items"]))

    def test_balanced_run_gets_its_own_filename_tag(self):
        # An auto-generated name must not share a stem with the recorded
        # prefix-slice dev baselines, or a 3-item smoke run gets read as a
        # rival to the 60-item dev numbers.
        with tempfile.TemporaryDirectory() as tmp:
            data = self.write_fixture(tmp)
            data_dir = Path(tmp) / "data-out"
            data_dir.mkdir()
            argv = ["eval_nli.py", "--data", str(data), "--limit", "3",
                    "--sampler", "balanced", "--backend", "lexical"]
            buf = io.StringIO()
            with patch.object(sys, "argv", argv), \
                    patch.object(eval_nli, "DATA_DIR", data_dir), \
                    contextlib.redirect_stdout(buf):
                eval_nli.main()
            names = sorted(p.name for p in data_dir.glob("eval_results_*.json"))
            self.assertEqual(len(names), 1)
            self.assertIn("_dev_lexical_oracle_balanced", names[0])
            # prefix mode keeps the untagged stem, i.e. it stays comparable
            # with the recorded dev baselines
            argv = ["eval_nli.py", "--data", str(data), "--limit", "3",
                    "--backend", "lexical"]
            with patch.object(sys, "argv", argv), \
                    patch.object(eval_nli, "DATA_DIR", data_dir), \
                    contextlib.redirect_stdout(buf):
                eval_nli.main()
            names = sorted(p.name for p in data_dir.glob("eval_results_*.json"))
            self.assertEqual(len(names), 2)
            self.assertIn("_dev_lexical_oracle.json",
                          [n for n in names if not n.endswith("_balanced.json")][0])


if __name__ == "__main__":
    unittest.main(verbosity=2)