"""P0 plumbing regressions; deterministic doubles do not measure model quality."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import booklet_app as app


class VoteContracts(unittest.TestCase):
    def test_candidate_prompt_has_one_complete_output_contract(self):
        messages = app.build_messages('Claim', '[e1; page 1]\nProposal A', vote='Proposal A',
                                      pipeline_version=app.CANDIDATE_PIPELINE)
        system = messages[0]['content']
        self.assertEqual(system.count('Reply with exactly one JSON object'), 1)
        self.assertIn('It must contain every one of these six fields', system)
        for field in ('label', 'reasoning', 'vote_status', 'vote_reference',
                      'evidence_status', 'evidence_refs'):
            self.assertIn('"' + field + '"', system)
        self.assertIn('Never omit any field.', system)
        self.assertLess(system.index('Resolve the specified vote'),
                        system.index('Reply with exactly one JSON object'))

    def test_nine_language_pairs_keep_vote_claim_and_conflicting_speakers(self):
        claims = {'de': 'Der Bundesrat empfiehlt ein Nein.',
                  'fr': 'Le Conseil fédéral recommande le non.',
                  'it': 'Il Consiglio federale raccomanda un no.'}
        texts = {
            'de': 'Vorlage A: Bundesrat Nein; Parlament Ja; Befürworter Ja; Gegner Nein. Vorlage B: Bundesrat Ja.',
            'fr': 'Projet A : Conseil fédéral Non ; Parlement Oui ; partisans Oui ; opposants Non. Projet B : Conseil fédéral Oui.',
            'it': 'Proposta A: Consiglio federale No; Parlamento Sì; promotori Sì; oppositori No. Proposta B: Consiglio federale Sì.'}
        for lang, text in texts.items():
            doc = {'source': 'votes.pdf', 'sha256': 'fixture', 'language': lang,
                   'pages': [{'page': 2, 'text': text}]}
            for claim in claims.values():
                for vote in ('Vorlage A', 'Projet B'):
                    with self.subTest(lang=lang, claim=claim, vote=vote):
                        request = {'id': 'vote', 'booklet': {'path': 'votes.pdf'},
                                   'claim': {'text': claim}, 'vote': vote}
                        retriever, judge = Mock(), Mock()
                        retriever.retrieve.return_value = app.passages(doc)
                        judge.judge.return_value = {'label': 'neutral', 'label_code': 1,
                                                    'vote_status': 'recognised', 'vote_reference': {'passage_id': 'e1'}, 'evidence_snippet': '',
                                                    'evidence_status': 'insufficient', 'evidence_refs': []}
                        result = app.classify(request, judge, retriever, doc)
                        self.assertEqual(result['claim'], claim)
                        self.assertEqual(retriever.retrieve.call_args.args[1], 'Vote: ' + vote + '\nClaim: ' + claim)
                        self.assertEqual(retriever.retrieve.call_args.args[2], 5)
                        self.assertEqual(judge.judge.call_args.args[0], claim)
                        self.assertEqual(judge.judge.call_args.kwargs['vote'], vote)
                        messages = app.build_messages(claim, text, vote=vote,
                                                      pipeline_version=app.CANDIDATE_PIPELINE)
                        self.assertIn(text, messages[1]['content'])
                        self.assertIn('## Claim\n' + claim + '\n', messages[1]['content'])
                        self.assertIn(json.dumps(vote), messages[1]['content'])
                        self.assertIn('disagreement between speakers does not contradict', messages[0]['content'])

    def test_ambiguous_unrecognised_and_missing_status_are_errors(self):
        doc = {'source': 'votes.pdf', 'sha256': 'fixture', 'language': 'de',
               'pages': [{'page': 1, 'text': 'Two proposals.'}]}
        request = {'claim': 'Claim', 'booklet': 'votes.pdf', 'vote': 'Proposal',
                   'evidence': 'full', 'pipeline_version': app.CANDIDATE_PIPELINE}
        for status, error in (('ambiguous', 'vote_ambiguous'),
                              ('unrecognised', 'vote_unrecognised'), (None, 'invalid_vote_status')):
            judge = Mock()
            judge.judge.return_value = {'label': 'entailment', 'label_code': 0, 'vote_status': status}
            result = app.classify(request, judge, booklet=doc)
            self.assertEqual(result['error'], error)
            self.assertIsNone(result['label'])
            self.assertIsNone(result['label_code'])

    def test_vote_changes_dense_ranking_without_changing_the_claim(self):
        import numpy as np
        import types
        class Encoder:
            def encode(self, texts, lang_code):
                return np.array([[1., 0.] if 'Vote A' in text else [0., 1.] for text in texts])
        module = types.SimpleNamespace(Retriever=Encoder, LANG_TO_ADAPTER={'de': 'de_CH'},
                                       cosine_sim_matrix=lambda q, d: (q @ d.T)[0])
        doc = {'source': 'votes.pdf', 'sha256': 'fixture', 'language': 'de',
               'pages': [{'page': 1, 'text': 'Vote A: Council rejects; proponents support.'},
                         {'page': 2, 'text': 'Vote B: Council supports; opponents reject.'}]}
        pages = []
        with patch.dict(sys.modules, {'retriever': module}):
            retriever = app.BookletRetriever()
            for vote in ('Vote A', 'Vote B'):
                judge = Mock()
                judge.judge.return_value = {'label': 'neutral', 'label_code': 1,
                    'vote_status': 'recognised', 'vote_reference': {'passage_id': 'e1'},
                    'evidence_status': 'insufficient', 'evidence_refs': []}
                result = app.classify({'id': 'vote', 'vote': vote,
                    'booklet': {'path': 'votes.pdf'}, 'claim': {'text': 'The Council supports it.'}},
                    judge, retriever, doc)
                pages.append(result['passages'][0]['page'])
                self.assertEqual(result['claim'], 'The Council supports it.')
        self.assertEqual(pages, [1, 2])

    def test_complete_vote_identity_is_accepted_and_missing_fields_are_rejected(self):
        selected = [{'id': 'e1', 'page': 1, 'page_start': 0, 'text': 'Proposal A'}]
        complete = {'label': 'neutral', 'label_code': 1, 'reasoning': 'Not stated.',
                    'vote_status': 'recognised', 'vote_reference': {'passage_id': 'e1'},
                    'evidence_status': 'insufficient', 'evidence_refs': []}
        accepted = app.candidate_result(dict(complete), selected, 'Proposal A')
        self.assertIsNone(accepted.get('error'))
        self.assertEqual(accepted['vote_citation']['text'], 'Proposal A')
        for missing in ('vote_status', 'vote_reference'):
            response = dict(complete)
            response.pop(missing)
            result = app.candidate_result(response, selected, 'Proposal A')
            self.assertIsNone(result['label'])
            self.assertTrue(result.get('error'))
        for ref in (None, {'passage_id': 'missing'}):
            response = dict(complete, vote_reference=ref)
            result = app.candidate_result(response, selected, 'Proposal A')
            self.assertIsNone(result['label'])
            self.assertTrue(result.get('error'))

    def test_frozen_flat_request_keeps_original_query_and_prompt(self):
        doc = {'source': 'votes.pdf', 'sha256': 'fixture', 'language': 'de',
               'pages': [{'page': 1, 'text': 'Evidence'}]}
        retriever, judge = Mock(), Mock()
        retriever.retrieve.return_value = app.passages(doc)
        judge.judge.return_value = {'label': 'neutral', 'label_code': 1}
        result = app.classify({'claim': 'Original claim', 'booklet': 'votes.pdf', 'vote': 'Vote'},
                              judge, retriever, doc)
        self.assertEqual(retriever.retrieve.call_args.args[1], 'Original claim')
        self.assertEqual(judge.judge.call_args.kwargs, {'seed': 20261011})
        self.assertEqual(result['pipeline_version'], app.FROZEN_PIPELINE)
        self.assertEqual(app.build_messages('Original claim', 'Evidence'),
                         [{'role': 'system', 'content': app.SYSTEM_PROMPT},
                          {'role': 'user', 'content': app.USER_TEMPLATE.format(claim='Original claim', evidence='Evidence')}])


class CitationContracts(unittest.TestCase):
    def result(self, refs, status='sufficient', snippet='A paraphrase, never a quotation'):
        doc = {'source': 'votes.pdf', 'sha256': 'fixture', 'language': 'it',
               'pages': [{'page': 7, 'text': 'Titolo. Più abita\u00ad\nzioni, non meno. Sì!'}]}
        judge = Mock()
        judge.judge.return_value = {'label': 'entailment', 'label_code': 0,
            'vote_status': 'recognised', 'vote_reference': {'passage_id': 'e1'}, 'evidence_status': status, 'evidence_refs': refs,
            'evidence_snippet': snippet, 'input_tokens': 42,
            'usage': {'completion_tokens': 12}, 'inference_s': 0.1}
        result = app.classify({'id': 'citation', 'claim': 'Claim', 'booklet': 'votes.pdf',
                               'vote': 'Vote', 'evidence': 'full',
                               'pipeline_version': app.CANDIDATE_PIPELINE}, judge, booklet=doc)
        return result, doc

    def test_exact_offsets_and_pdf_extraction_artefacts(self):
        result, doc = self.result([{'passage_id': 'e1', 'start': 8, 'end': 31}])
        citation = result['citations'][0]
        text = doc['pages'][0]['text'][8:31]
        self.assertEqual(citation['text'], text)
        self.assertEqual((citation['page_start'], citation['page_end']), (8, 31))
        self.assertEqual(citation['page'], 7)
        self.assertEqual(citation['pdf_sha256'], doc['sha256'])
        self.assertEqual(app.submission_output(result)['evidence'], [{'page': 7, 'text': text}])
        self.assertIn('\u00ad\n', text)

    def test_paraphrase_is_not_emitted_and_no_reference_is_not_repaired(self):
        result, doc = self.result([{'passage_id': 'e1'}])
        self.assertEqual(app.submission_output(result)['evidence'][0]['text'], doc['pages'][0]['text'])
        result, _ = self.result([])
        self.assertEqual(result['error'], 'insufficient_evidence')
        self.assertEqual(result['citations'], [])
        with self.assertRaises(ValueError):
            app.submission_output(result)

    def test_invalid_offsets_ids_and_insufficient_evidence_fail(self):
        refs = [{'passage_id': 'e2'}, {'passage_id': 'e1', 'start': -1, 'end': 3},
                {'passage_id': 'e1', 'start': True, 'end': 3},
                {'passage_id': 'e1', 'start': 0, 'end': 1000},
                {'passage_id': 'e1', 'start': 3, 'end': 3},
                {'passage_id': 'e1', 'start': 0}, {'passage_id': 'e1', 'end': 3}]
        for ref in refs:
            result, _ = self.result([ref])
            self.assertIsNone(result['label'])
            self.assertFalse(result['citation_verified'])
        result, _ = self.result([{'passage_id': 'e1'}], status='insufficient')
        self.assertEqual(result['error'], 'insufficient_evidence')

    def test_ambiguous_source_requires_offsets_and_citations_are_rechecked(self):
        doc = {'source': 'votes.pdf', 'sha256': 'fixture', 'language': 'de',
               'pages': [{'page': 1, 'text': 'Ja. Nein. Ja.'}]}
        passage = {'page': 1, 'text': 'Ja.', 'source': 'votes.pdf', 'pdf_sha256': 'fixture'}
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            app.source_passages(doc, [passage])
        located = app.source_passages(doc, [dict(passage, page_start=10, page_end=13)])
        self.assertEqual(located[0]['page_start'], 10)
        with self.assertRaisesRegex(ValueError, 'Invalid source'):
            app.source_passages(doc, [dict(passage, page_start=1, page_end=4)])
        result, _ = self.result([{'passage_id': 'e1'}])
        result['citations'][0]['text'] = 'An unrelated passage.'
        with self.assertRaisesRegex(ValueError, 'citation_source_mismatch'):
            app.submission_output(result)


class EndpointContracts(unittest.TestCase):
    def judge(self, raw=None, **changes):
        judge = object.__new__(app.SubmissionJudge)
        judge.model, judge.context, judge.max_tokens = app.MODEL, 32768, 512
        judge.base, judge.session = 'https://test', Mock()
        reply = {'model': app.MODEL, 'choices': [{'message': {'content': raw or json.dumps({
            'label': 'neutral', 'vote_status': 'recognised', 'vote_reference': {'passage_id': 'e1'}, 'evidence_status': 'insufficient',
            'evidence_refs': []})}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 42, 'completion_tokens': 20}}
        reply.update(changes)
        judge.session.post.return_value.json.return_value = reply
        return judge

    def call(self, judge):
        with patch.dict(app.os.environ, {'LLM_TOKEN_PREFLIGHT': 'optional'}, clear=True):
            return judge.judge('Original claim', '[e1; page 1] Evidence', vote='Vote',
                               pipeline_version=app.CANDIDATE_PIPELINE)

    def test_optional_tokenize_and_candidate_response_contract(self):
        judge = self.judge(json.dumps({'label': 'entailment', 'reasoning': 'The passage supports the claim.',
                                      'vote_status': 'recognised', 'vote_reference': {'passage_id': 'e1'},
                                      'evidence_status': 'sufficient',
                                      'evidence_refs': [{'passage_id': 'e1'}]}))
        result = self.call(judge)
        self.assertEqual(result['label_code'], 0)
        self.assertEqual(result['evidence_refs'], [{'passage_id': 'e1'}])
        self.assertEqual(judge.session.post.call_count, 1)
        self.assertEqual(judge.session.post.call_args.args[0], 'https://test/v1/chat/completions')
        self.assertEqual(result['input_tokens'], 42)
        self.assertGreaterEqual(result['inference_s'], 0)

    def test_candidate_recovers_exactly_one_extra_trailing_brace(self):
        raw = json.dumps({
            'label': 'entailment', 'reasoning': 'The passage supports the claim.',
            'vote_status': 'recognised', 'vote_reference': {'passage_id': 'e1'},
            'evidence_status': 'sufficient',
            'evidence_refs': [{'passage_id': 'e1'}]}, separators=(',', ':')) + '}'
        result = self.call(self.judge(raw))
        self.assertEqual(result['label_code'], 0)
        self.assertEqual(result['raw_response'], raw)
        self.assertEqual(result['syntax_recovery'],
                         'removed_single_trailing_closing_brace')
        self.assertEqual(result['vote_status'], 'recognised')
        self.assertEqual(result['evidence_refs'], [{'passage_id': 'e1'}])

    def test_candidate_recovery_rejects_other_malformed_or_ambiguous_json(self):
        complete = json.dumps({
            'label': 'neutral', 'reasoning': 'Insufficient evidence.',
            'vote_status': 'recognised', 'vote_reference': {'passage_id': 'e1'},
            'evidence_status': 'insufficient', 'evidence_refs': []},
            separators=(',', ':'))
        malformed = (
            complete + '}}',
            complete + ' trailing',
            complete + complete + '}',
            complete.replace('"label":"neutral"',
                             '"label":"entailment","label":"neutral"') + '}',
            '[' + complete + ']}'
        )
        for raw in malformed:
            with self.subTest(raw=raw):
                result = self.call(self.judge(raw))
                self.assertIsNone(result['label'])
                self.assertTrue(result['error'].startswith('model_response_parse_error:'))
                self.assertNotIn('syntax_recovery', result)
                self.assertEqual(result['raw_response'], raw)

    def test_candidate_parse_errors_are_not_endpoint_errors(self):
        raw = '{"label":"neutral",'
        result = self.call(self.judge(raw))
        self.assertEqual(result['error'], 'model_response_parse_error:JSONDecodeError')
        self.assertEqual(result['raw_response'], raw)

    def test_malformed_incomplete_responses_and_token_usage_fail(self):
        for raw in ('neutral', '{"label":"neutral",',
                    '{"label":"entailment","label":"neutral"}',
                    '{"label":"neutral","evidence_refs":NaN}', '[]'):
            result = self.call(self.judge(raw))
            self.assertIsNone(result['label'])
            self.assertTrue(result.get('error'))
        for fields in ({'choices': []}, {'model': 'wrong'}, {'usage': {}},
                       {'usage': {'prompt_tokens': True, 'completion_tokens': 20}},
                       {'usage': {'prompt_tokens': 42, 'completion_tokens': 513}},
                       {'usage': {'prompt_tokens': 42, 'completion_tokens': 20, 'total_tokens': 100}},
                       {'choices': [{'message': {'content': '{}'}, 'finish_reason': 'length'}]}):
            result = self.call(self.judge(**fields))
            self.assertIsNone(result['label'])
            self.assertTrue(result.get('error'))

    def test_unknown_tasks_ids_conflicting_shapes_and_nonfinite_metrics(self):
        for changes in ({'task': 'unknown'}, {'id': ''}, {'booklet': 'votes.pdf'}):
            request = dict({'id': 'test', 'task': 'beginner', 'claim': 'Claim', 'reference': 'Evidence'}, **changes)
            with self.assertRaises(ValueError):
                app.validate_request(request)
        base = {'label': 'neutral', 'label_code': 1, 'case_id': 'metrics',
                'input_tokens': 42, 'usage': {'completion_tokens': 20}}
        for latency in (float('nan'), float('inf'), -1, True):
            with self.assertRaisesRegex(ValueError, 'latency'):
                app.submission_output(dict(base, inference_s=latency))

    def test_model_listing_and_endpoint_errors_do_not_record_credentials(self):
        env = {'LLM_NAME': app.MODEL, 'LLM_BASE_URL': 'https://test', 'LLM_API_KEY': 'dummy-only'}
        for listing in ({}, [], {'data': [{}]}, {'data': 'not-a-list'}):
            session = Mock()
            session.headers = {}
            session.get.return_value.json.return_value = listing
            with patch.dict(app.os.environ, env, clear=True), patch('requests.Session', return_value=session):
                with self.assertRaises(ValueError):
                    app.SubmissionJudge()
        import requests
        judge = self.judge()
        judge.session.post.side_effect = requests.ConnectionError('dummy-only private response')
        result = self.call(judge)
        self.assertIsNone(result['label'])
        self.assertNotIn('dummy-only', json.dumps(result))


if __name__ == '__main__':
    unittest.main()
