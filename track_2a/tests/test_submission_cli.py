import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import submission_cli as cli
import booklet_app as app


class Contracts(unittest.TestCase):
    def case(self, id="b"):
        return {"id":id,"vote":"Proposal","claim":{"text":"Claim","language":"de"},"reference":{"text":"Source","language":"fr"}}

    def test_mixed_batch_local_paths_compact_jsonl_and_retriever_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'booklets').mkdir();(root/'booklets/x.pdf').write_bytes(b'%PDF-fake')
            a=self.case('a');a.pop('reference');a['booklet']={'path':'booklets/x.pdf','language':'fr'}
            b=self.case();source=root/'cases.jsonl';source.write_text('\n'.join(map(json.dumps,[a,b,a|{'id':'a2'}])))
            output=root/'output/predictions.jsonl';factory=Mock(return_value=object())
            def classify(req,judge,retriever=None,booklet=None):
                if req['task']=='advanced':self.assertEqual(req['booklet'],str((root/'booklets/x.pdf').resolve()))
                return {'id':req['id'],'label':1,'label_name':'neutral','evidence':[], 'metrics':{'input_tokens':4,'output_tokens':2,'inference_time_ms':1}}
            with patch.object(app,'load_booklet',return_value={}) as load,patch.object(app,'classify',side_effect=classify),patch.object(app,'submission_output',side_effect=lambda x:x):
                self.assertEqual(cli.run(source,output,root,lambda:object(),factory),0)
            self.assertEqual([json.loads(x)['id'] for x in output.read_text().splitlines()],['a','b','a2'])
            factory.assert_called_once()
            load.assert_called_once()
            self.assertEqual(len(output.read_text().splitlines()),3)

    def test_duplicate_and_ambiguous_input_rejected_before_inference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'cases.jsonl';p.write_text('\n'.join([json.dumps(self.case())]*2))
            factory=Mock()
            with self.assertRaises(ValueError):cli.run(p,root/'out',root,factory)
            factory.assert_not_called()
            bad=self.case();bad['booklet']={'path':'https://example.test/book.pdf'};p.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):cli.read_cases(p,root)

    def test_booklet_paths_cannot_escape_data_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);data=root/'data';data.mkdir();outside=root/'outside.pdf';outside.write_bytes(b'%PDF-fake')
            source=data/'cases.jsonl'
            for path in (str(outside), '../outside.pdf'):
                case=self.case();case.pop('reference');case['booklet']={'path':path}
                source.write_text(json.dumps(case))
                with self.subTest(path=path),self.assertRaisesRegex(ValueError,'beneath data root'):
                    cli.read_cases(source,data)
            link=data/'linked.pdf'
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest('symlinks unavailable')
            case=self.case();case.pop('reference');case['booklet']={'path':'linked.pdf'}
            source.write_text(json.dumps(case))
            with self.assertRaisesRegex(ValueError,'beneath data root'):
                cli.read_cases(source,data)

    def test_evaluation_output_must_remain_beneath_output_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);data=root/'data';output=root/'output';data.mkdir();output.mkdir()
            source=data/'cases.jsonl';source.write_text(json.dumps(self.case()))
            with self.assertRaisesRegex(ValueError,'beneath output root'):
                cli.run(source,root/'escape.jsonl',data,lambda:object(),output_root=output)

    def test_failure_does_not_drop_later_case_or_guess_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'cases.jsonl';p.write_text('\n'.join(json.dumps(self.case(x)) for x in ['bad','good']))
            response={'id':'good','label':1,'label_name':'neutral','evidence':[],'metrics':{}}
            with patch.object(app,'classify',side_effect=[ValueError(),response]),patch.object(app,'submission_output',side_effect=lambda x:x):
                self.assertEqual(cli.run(p,root/'out',root,lambda:object()),1)
            rows = [json.loads(line) for line in (root/'out').read_text().splitlines()]
            self.assertEqual([row['id'] for row in rows], ['bad', 'good'])
            self.assertIsNone(rows[0]['label'])
            self.assertIn('error', rows[0])

    def test_proxy_variables_override_development_aliases(self):
        with patch.dict(os.environ,{'BASE_URL':'http://proxy.test/v1','API_KEY':'test-secret','LLM_BASE_URL':'http://wrong.test','LLM_API_KEY':'wrong'},clear=True),patch('sys.argv',['submission_cli','--input','cases','--output','out']),patch.object(cli,'run',return_value=0) as run:
            self.assertEqual(cli.main(),0)
            self.assertEqual(os.environ['LLM_BASE_URL'],'http://proxy.test/v1')
            self.assertEqual(os.environ['LLM_API_KEY'],'test-secret')
            run.assert_called_once()

class ClientIntegration(unittest.TestCase):
    def test_reference_through_injected_proxy_with_mock_http_transport(self):
        model="swiss-ai/Apertus-v1.5-70B"
        parsed={'label':'entailment','reasoning':'Same statement','vote_status':None,'vote_reference':None,'evidence_status':'sufficient','evidence_refs':[{'passage_id':'e1'}]}
        session=Mock();session.headers={}
        session.get.return_value.json.return_value={'data':[{'id':model}]}
        session.post.return_value.json.return_value={'model':model,'choices':[{'message':{'content':json.dumps(parsed)},'finish_reason':'stop'}],'usage':{'prompt_tokens':100,'completion_tokens':30}}
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'BASE_URL':'http://proxy.test/v1','API_KEY':'dummy','LLM_TOKEN_PREFLIGHT':'optional','LLM_NAME':model},clear=False),patch('requests.Session',return_value=session):
            root=Path(tmp);source=root/'cases.jsonl';out=root/'predictions.jsonl'
            source.write_text(json.dumps({'id':'http-B','vote':'Proposal','reference':{'text':'The council says no.'},'claim':{'text':'The council says no.'}})+'\n')
            self.assertEqual(cli.run(source,out,root),0)
            result=json.loads(out.read_text());self.assertEqual(result['label'],0)
            self.assertEqual(result['evidence'],[{'page':None,'text':'The council says no.'}])
            self.assertEqual(result['metrics']['input_tokens'],100)
            session.get.assert_not_called()
            self.assertIn('Proposal', session.post.call_args.kwargs['json']['messages'][1]['content'])
            self.assertEqual(session.post.call_args.args[0],'http://proxy.test/v1/chat/completions')
            self.assertEqual(session.headers['Authorization'],'Bearer dummy')


class EvaluationP0(unittest.TestCase):
    def test_task_b_optional_citations_all_labels_and_language_pairs(self):
        for source_language in app.LANGUAGES:
            for claim_language in app.LANGUAGES:
                for label in ('entailment', 'neutral', 'contradiction'):
                    judge = Mock()
                    judge.judge.return_value = {
                        'label': label, 'label_code': app.label_to_code(label),
                        'input_tokens': 8, 'usage': {'completion_tokens': 3}, 'inference_s': .02}
                    request = {'id': 'b', 'vote': 'Réforme',
                               'reference': {'text': 'Premise', 'language': source_language},
                               'claim': {'text': 'Claim', 'language': claim_language}}
                    result = app.classify(request, judge)
                    self.assertEqual(app.submission_output(result)['label'], app.label_to_code(label))
                    self.assertEqual(app.submission_output(result)['evidence'], [])
                    self.assertEqual(judge.judge.call_args.kwargs['vote'], 'Réforme')
                    self.assertTrue(judge.judge.call_args.kwargs['reference_task'])

    def test_proxy_precedence_and_wrong_response_model_rejected(self):
        session = Mock(); session.headers = {}
        session.post.return_value.json.return_value = {'model': 'other-model'}
        with patch.dict(os.environ, {'BASE_URL': 'http://proxy.test/v1', 'API_KEY': 'dummy',
                                    'LLM_BASE_URL': 'http://wrong.test', 'LLM_API_KEY': 'wrong',
                                    'LLM_NAME': app.CSCS_MODEL}, clear=True), \
                patch('requests.Session', return_value=session):
            judge = app.SubmissionJudge()
            result = judge.judge('Claim', 'Source')
        session.get.assert_not_called()
        self.assertEqual(session.headers['Authorization'], 'Bearer dummy')
        self.assertEqual(session.post.call_args.args[0], 'http://proxy.test/v1/chat/completions')
        self.assertEqual(result['error'], 'response_model_mismatch_or_missing')
        self.assertIsNone(result['label'])

    def test_actual_adapter_selection_all_nine_language_pairs(self):
        import types
        import numpy as np
        encoder = Mock()
        encoder.encode.return_value = np.array([[1., 0.]])
        adapters = {'de': 'de_CH', 'fr': 'fr_CH', 'it': 'it_CH'}
        module = types.SimpleNamespace(Retriever=lambda: encoder, LANG_TO_ADAPTER=adapters,
                                       cosine_sim_matrix=lambda q, d: np.array([1.]))
        with patch.dict('sys.modules', {'retriever': module}):
            for source_language in app.LANGUAGES:
                for claim_language in app.LANGUAGES:
                    encoder.reset_mock()
                    booklet = {'source': 'x.pdf', 'sha256': 'fixture', 'language': source_language,
                               'pages': [{'page': 1, 'text': 'Source'}]}
                    app.BookletRetriever().retrieve(booklet, claim_language + ' claim')
                    self.assertEqual([call.kwargs['lang_code'] for call in encoder.encode.call_args_list],
                                     [adapters[source_language]] * 2)

    def test_gold_fields_do_not_reach_model(self):
        judge = Mock()
        judge.judge.return_value = {'label': 'neutral', 'label_code': 1}
        request = {'id': 'b', 'vote': 'Proposal', 'reference': {'text': 'Premise'},
                   'claim': {'text': 'Claim'}, 'label': 'GOLD_SECRET', 'gold': 'GOLD_SECRET',
                   'reference_string': 'GOLD_SECRET'}
        app.classify(request, judge)
        self.assertNotIn('GOLD_SECRET', str(judge.judge.call_args))


if __name__ == "__main__":
    unittest.main()
