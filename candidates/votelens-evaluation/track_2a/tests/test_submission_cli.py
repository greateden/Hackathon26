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
            def classify(req,judge,retriever=None):
                if req['task']=='advanced':self.assertEqual(req['booklet'],str((root/'booklets/x.pdf').resolve()))
                return {'id':req['id'],'label':1,'label_name':'neutral','evidence':[], 'metrics':{'input_tokens':4,'output_tokens':2,'inference_time_ms':1}}
            with patch.object(app,'classify',side_effect=classify),patch.object(app,'submission_output',side_effect=lambda x:x):
                self.assertEqual(cli.run(source,output,root,lambda:object(),factory),0)
            self.assertEqual([json.loads(x)['id'] for x in output.read_text().splitlines()],['a','b','a2'])
            factory.assert_called_once()
            self.assertEqual(len(output.read_text().splitlines()),3)

    def test_duplicate_and_ambiguous_input_rejected_before_inference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'cases.jsonl';p.write_text('\n'.join([json.dumps(self.case())]*2))
            factory=Mock()
            with self.assertRaises(ValueError):cli.run(p,root/'out',root,factory)
            factory.assert_not_called()
            bad=self.case();bad['booklet']={'path':'https://example.test/book.pdf'};p.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):cli.read_cases(p,root)

    def test_failure_does_not_drop_later_case_or_guess_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'cases.jsonl';p.write_text('\n'.join(json.dumps(self.case(x)) for x in ['bad','good']))
            response={'id':'good','label':1,'label_name':'neutral','evidence':[],'metrics':{}}
            with patch.object(app,'classify',side_effect=[ValueError(),response]),patch.object(app,'submission_output',side_effect=lambda x:x):
                self.assertEqual(cli.run(p,root/'out',root,lambda:object()),1)
            self.assertEqual(json.loads((root/'out').read_text())['id'],'good')

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
            self.assertEqual(session.get.call_args.args[0],'http://proxy.test/v1/models')
            self.assertEqual(session.post.call_args.args[0],'http://proxy.test/v1/chat/completions')
            self.assertEqual(session.headers['Authorization'],'Bearer dummy')

if __name__=='__main__':unittest.main()
