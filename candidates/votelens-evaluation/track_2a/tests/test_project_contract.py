"""Offline regression checks over the evaluation path; no model is loaded.

Run from the repo root:
  PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
"""
import contextlib
import io
import json
import logging
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# The modules under test live in src/; scripts add that directory to
# sys.path themselves but a test file does not, so add it here to keep
# discovery independent of the working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import ablation_dev
import eval_nli
import main
from nli_judge import OpenAICompatJudge, build_chat, get_prompt_config
from hybrid_retrieval import (BM25, TwoStageRetriever, rrf_fuse,
                              index_cache_key)


class JudgePipelineContractTests(unittest.TestCase):
    def setUp(self):
        self.stdout = contextlib.redirect_stdout(io.StringIO())
        self.stdout.__enter__()
        self.addCleanup(self.stdout.__exit__, None, None, None)
        self.log = Mock(spec=logging.Logger)

    def judge_with_listing(self, ids):
        response = Mock()
        response.json.return_value = {'data': [{'id': x} for x in ids]}
        with patch('requests.get', return_value=response):
            return OpenAICompatJudge(model='org/model-v1')

    def test_identity_exact(self):
        self.assertEqual(self.judge_with_listing(['org/model-v1']).served,
                         ['org/model-v1'])

    def test_identity_substrings_rejected(self):
        for value in ['org', 'model-v1', 'org/model-v1-other', '', None, 3]:
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                self.judge_with_listing([value])

    def test_identity_endpoint_failure(self):
        with patch('requests.get', side_effect=RuntimeError('offline')):
            with self.assertRaisesRegex(RuntimeError, 'not reachable'):
                OpenAICompatJudge()

    def pipe(self, passages, verdict):
        pipe = main.Pipeline.__new__(main.Pipeline)
        pipe.mode = 'legacy'
        pipe.retrieval_config = 'legacy'
        pipe.retriever = Mock()
        pipe.retriever.retrieve.return_value = passages
        pipe.judge = Mock()
        pipe.judge.judge.return_value = verdict
        return pipe

    def test_empty_evidence_never_calls_judge(self):
        pipe = self.pipe([], {'label': 'neutral'})
        result = pipe.verify('claim')
        self.assertIsNone(result['label'])
        self.assertEqual(result['status'], 'error')
        pipe.judge.judge.assert_not_called()

    def test_backend_error_cannot_be_success(self):
        pipe = self.pipe([{'id': 'x', 'score': 1, 'text': 'evidence'}],
                         {'label': 'neutral', 'error': 'failed'})
        self.assertIsNone(pipe.verify('claim')['label'])

    def test_invalid_label_cannot_be_success(self):
        pipe = self.pipe([{'id': 'x', 'score': 1, 'text': 'evidence'}],
                         {'label': 'garbage'})
        self.assertEqual(pipe.verify('claim')['status'], 'error')

    def test_all_labels_preserved(self):
        for label, code in [('entailment', 0), ('neutral', 1), ('contradiction', 2)]:
            pipe = self.pipe([{'id': 'x', 'score': 1, 'text': 'evidence'}],
                             {'label': label})
            result = pipe.verify('claim')
            self.assertEqual((result['label'], result['label_code'], result['status']),
                             (label, code, 'ok'))

    def test_failed_claim_remains_in_batch(self):
        pipe = Mock()
        pipe.verify.side_effect = [RuntimeError('broken retrieval'),
                                  {'label': 'neutral', 'status': 'ok', 'retrieved': []}]
        rows = main.run(pipe, ['first', 'second'], self.log)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['claim'], 'first')
        self.assertEqual(rows[0]['status'], 'error')
        self.assertIsNone(rows[0]['label_code'])
        self.assertEqual(rows[1]['label'], 'neutral')

    def test_cli_failure_exit_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            pipe = Mock()
            pipe.verify.side_effect = RuntimeError('broken retrieval')
            with patch.object(main, 'Pipeline', return_value=pipe), \
                 patch.object(main, 'DATA_DIR', Path(tmp)), \
                 patch.object(main, 'make_logger', return_value=(self.log, None)), \
                 patch.object(sys, 'argv', ['main.py', 'claim']):
                self.assertEqual(main.main(), 1)
            reports = list(Path(tmp).glob('results_*.json'))
            self.assertEqual(len(reports), 1)
            result = json.loads(reports[0].read_text())['results']
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]['status'], 'error')

    def test_cli_missing_claims_exit(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(main, 'DATA_DIR', Path(tmp)), \
             patch.object(main, 'make_logger', return_value=(self.log, None)), \
             patch.object(sys, 'argv', ['main.py']):
            self.assertEqual(main.main(), 1)

    def test_ablation_reads_its_own_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            wrong = Path(tmp) / 'eval_results_unrelated.json'
            wrong.write_text('{"wrong": true}')
            def run(cmd, **kwargs):
                out = Path(cmd[cmd.index('--out') + 1])
                out.write_text(json.dumps({'meta': {'backend': 'lexical',
                    'evidence_mode': 'oracle', 'prompt_config': 't0', 'split': 'dev'},
                    'items': [], 'summary': {}}))
                # An unrelated run can finish after ours.
                import os
                os.utime(wrong, (4000000000, 4000000000))
                return Mock(returncode=0)
            with patch.object(ablation_dev, 'DATA_DIR', Path(tmp)), \
                 patch.object(ablation_dev.subprocess, 'run', side_effect=run):
                runs, ok = ablation_dev.run_combo('t0', 'oracle', 'lexical', 1)
            self.assertTrue(ok)
            self.assertNotEqual(runs[0][0], wrong)
            self.assertEqual(runs[0][1]['meta']['prompt_config'], 't0')

    def test_ablation_partial_run_exits_nonzero(self):
        payload = {'items': [], 'summary': {}}
        with patch.object(ablation_dev, 'run_combo', side_effect=[
                ([(Path('first.json'), payload)], True), ([], False)]), \
             patch.object(sys, 'argv', ['ablation_dev.py', '--backend', 'lexical']), \
             self.assertRaises(SystemExit):
            ablation_dev.main()

    def test_eval_explicit_output_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'keep.json'
            out.write_text('original')
            with patch.object(sys, 'argv', ['eval_nli.py', '--out', str(out)]), \
                 self.assertRaises(SystemExit):
                eval_nli.main()
            self.assertEqual(out.read_text(), 'original')

    def test_eval_explicit_output_integration(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'result.json'
            data = Path(tmp) / 'data.jsonl'
            data.write_text(json.dumps({'claim': 'example', 'entailment_label': 1,
                'reference_string': 'plain evidence', 'reference_language': 'de'}))
            with patch.object(sys, 'argv', ['eval_nli.py', '--out', str(out),
                    '--data', str(data), '--backend', 'lexical']):
                eval_nli.main()
            result = json.loads(out.read_text())
            self.assertEqual(result['summary']['n'], 1)
            self.assertEqual(result['items'][0]['pred'], 'neutral')

    def test_metrics_hand_calculated_with_errors(self):
        # E: TP=1, FN=1, FP=1 => F1=1/2; N: TP=1,FN=1 => 2/3;
        # C: TP=0,FN=1 => 0; accuracy=2/5; rounded macro=0.389.
        pairs = [('entailment','entailment'),('entailment',None),
                 ('neutral','neutral'),('neutral','entailment'),('contradiction',None)]
        rows = [{'gold': g, 'pred': p, 'correct': g == p, 'elapsed_s': 0}
                for g,p in pairs]
        summary = eval_nli.summarise(rows)
        self.assertEqual(summary['accuracy'], .4)
        self.assertEqual(summary['macro_f1'], .389)
        self.assertEqual(summary['errors'], 2)
        self.assertEqual(summary['confusion']['contradiction']['ERROR'], 1)
        self.assertEqual(eval_nli.summarise([])['n'], 0)

    def test_retrieval_metrics_independent_fixture(self):
        from eval_e2e import eval_config
        records = [{'claim_language': 'de', 'reference_language': 'de'}] * 4
        gold = {0:{'gold':{0},'doc_id':'a'},1:{'gold':{1},'doc_id':'b'},
                2:{'gold':set(),'doc_id':'b'},3:{'gold':{1},'doc_id':'b'}}
        result = eval_config('fixture', records, gold,
                             [[(0,1)], [(0,1),(1,.5)], [], []],
                             [{'doc_id':'a'},{'doc_id':'b'}])
        self.assertEqual(result['n_scored'], 3)
        self.assertEqual(result['recall'], {'r@1':.3333,'r@3':.6667,'r@5':.6667})
        self.assertEqual(result['mrr@5'], .5)
        self.assertEqual(result['doc_routing_top1'], .3333)

    def test_rrf_manual(self):
        fused = rrf_fuse([[(0,9),(1,8)],[(1,100)]], k=1)
        self.assertEqual([i for i,s in fused], [1,0])
        self.assertAlmostEqual(fused[0][1], 1/3 + 1/2)

    def test_corpus_order_changes_cache_key(self):
        corpus = [{'lang':'de','text':'one'}, {'lang':'fr','text':'two'}]
        self.assertNotEqual(index_cache_key(corpus), index_cache_key(corpus[::-1]))

    def test_index_alignment_with_fake_encoder(self):
        import numpy as np
        from retriever import Retriever
        ret = Retriever.__new__(Retriever)
        ret.encode = lambda texts, lang_code: np.array([[int(t),len(lang_code)] for t in texts])
        corpus = [{'lang':'fr','text':'1'}, {'lang':'de','text':'2'},
                  {'lang':'fr','text':'3'}]
        ret.build_index(corpus)
        self.assertEqual(ret.corpus_embeddings[:,0].tolist(), [1,2,3])

    def test_prompt_equivalence_boundary(self):
        for size in [0, 1, 1900, 1990, 2000, 3000]:
            passages = [{'id':'x', 'lang':'fr', 'text':'a' * size}] * 2
            for left,right in [('fill_only','select'),('window_only','t0')]:
                self.assertEqual(build_chat(get_prompt_config(left),'claim',passages),
                                 build_chat(get_prompt_config(right),'claim',passages))


class LexicalProtocolTests(unittest.TestCase):
    """D01 guards. The lexical channel is only a fair baseline if documents
    and queries go through the same analyser, and the choice must reach the
    hybrid/two-stage stacks (not just the standalone `lexical_v2` config).
    Offline: no encoder is loaded."""

    CORPUS = [
        {"id": "a0", "doc_id": "de_1985_001", "lang": "de",
         "text": "Abstimmung ueber das BAHNNETZ. Ausbau und Ausbau."},
        {"id": "a1", "doc_id": "de_1985_001", "lang": "de",
         "text": "Chaese und Schokolade in den Alpen."},
        {"id": "a2", "doc_id": "fr_1985_002", "lang": "fr",
         "text": "Le fromage et le chocolat dans les Alpes."},
    ]

    def test_asym_index_keeps_raw_tokens(self):
        b = BM25([r["text"] for r in self.CORPUS])
        self.assertEqual(b.protocol, "lex-asym-v1")
        self.assertIn("BAHNNETZ.", b.index)      # unmatchable by design
        self.assertNotIn("bahnnetz", b.index)

    def test_query_term_recoverable_only_after_normalisation(self):
        # Shape of the §5.4 defect: the query analyser strips punctuation and
        # case, so a term indexed raw can never score. lex-asym-v1 therefore
        # returns nothing at all for a query that lex-sym-v2 answers.
        asym = BM25([r["text"] for r in self.CORPUS])
        sym = BM25([r["text"] for r in self.CORPUS], norm_docs=True)
        self.assertEqual(asym.top_k("bahnnetz", 3), [])
        top = sym.top_k("bahnnetz", 3)
        self.assertTrue(top)
        self.assertEqual(top[0][0], 0)

    def test_two_stage_receives_the_configured_protocol(self):
        kw = dict(mode="two_stage", use_dense=False, doc_top_n=1,
                  cand_per_source=2)
        legacy = TwoStageRetriever(self.CORPUS, **kw)   # default = asym
        sym = TwoStageRetriever(self.CORPUS, lex_protocol="sym", **kw)
        self.assertEqual(legacy.passage_bm25.protocol, "lex-asym-v1")
        self.assertEqual(legacy.doc_bm25.protocol, "lex-asym-v1")
        self.assertEqual(sym.passage_bm25.protocol, "lex-sym-v2")
        self.assertEqual(sym.doc_bm25.protocol, "lex-sym-v2")
        legacy_ids = [i for i, _ in legacy.retrieve("bahnnetz", 2)]
        sym_ids = [i for i, _ in sym.retrieve("bahnnetz", 2)]
        self.assertNotIn(0, legacy_ids)
        self.assertIn(0, sym_ids)

    def test_harness_defaults_keep_the_legacy_path_reproducible(self):
        src = (Path(__file__).resolve().parent.parent
               / "src" / "eval_e2e.py").read_text(encoding="utf-8")
        # Default must stay asymmetric so the recorded §5.4 asym run is
        # reproducible; the symmetric channel has to be selectable and must
        # actually reach TwoStageRetriever instead of being hard-coded.
        self.assertIn('"--lex-protocol"', src)
        self.assertIn('choices=["asym", "sym"]', src)
        self.assertIn('default="asym"', src)
        self.assertIn("lex_protocol=args.lex_protocol", src)


class RecordedBenchmarkTests(unittest.TestCase):
    """The recorded benchmark files are the evidence behind §5.4, so their
    provenance is checked here: a run that silently reuses the defective
    lexical channel must not be reported as a corrected comparison."""

    HERE = Path(__file__).resolve().parent.parent / "data"

    def test_sym_run_is_recorded_and_differs_from_the_asym_run(self):
        legacy_p = self.HERE / "eval_results_full_benchmark.json"
        sym_p = self.HERE / "eval_results_full_symlex.json"
        if not (legacy_p.exists() and sym_p.exists()):
            self.skipTest("benchmark artefacts not built")
        legacy = json.loads(legacy_p.read_text(encoding="utf-8"))
        sym = json.loads(sym_p.read_text(encoding="utf-8"))
        self.assertEqual(
            sym["protocol_versions"]["hybrid_lexical"],
            "lex-sym-v2 (norm_text on both sides)")
        for cfg in ("hyb_rrf", "two_stage_lex", "two_stage"):
            self.assertIn(cfg, sym["configs"], cfg)
            # Both lexical legs differ, so the two files cannot be the same
            # measurement and the corrected numbers cannot be stale copies.
            self.assertNotEqual(sym["configs"][cfg]["recall"]["r@5"],
                                legacy["configs"][cfg]["recall"]["r@5"], cfg)

    def test_dense_config_does_not_leak_gold_language_by_default(self):
        sym_p = self.HERE / "eval_results_full_symlex.json"
        if not sym_p.exists():
            self.skipTest("benchmark artefacts not built")
        sym = json.loads(sym_p.read_text(encoding="utf-8"))
        # A deployable run must not consult the gold reference language.
        self.assertEqual(sym["adapter_policy"], "claim")
        self.assertFalse(sym["integrity"]["adapter_policy_uses_gold_language"])


if __name__ == '__main__':
    unittest.main()
