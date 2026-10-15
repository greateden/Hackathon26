"""Offline prompt/contract fixtures, not a test of model semantic accuracy."""
import json
import unittest
from unittest.mock import Mock, patch

import booklet_app as app
from experimental_vote_identity import VOTE_IDENTITY_INSTRUCTIONS, VOTE_IDENTITY_V1


class ExperimentalVoteIdentity(unittest.TestCase):
    def test_only_instruction_changes_and_default_remains_identical(self):
        kwargs = dict(vote='Proposal A', pipeline_version=app.CANDIDATE_PIPELINE)
        baseline = app.build_messages('Claim', 'Evidence', **kwargs)
        explicit = app.build_messages('Claim', 'Evidence', app.SYSTEM_PROMPT, **kwargs)
        candidate = app.build_messages('Claim', 'Evidence', VOTE_IDENTITY_V1, **kwargs)
        self.assertEqual(baseline, explicit)
        self.assertEqual(candidate[1], baseline[1])
        self.assertEqual(candidate[0]['content'].replace('\n\n' + VOTE_IDENTITY_INSTRUCTIONS, ''),
                         baseline[0]['content'])
        self.assertEqual(candidate[0]['content'].count(app.CANDIDATE_OUTPUT_CONTRACT), 1)
        self.assertEqual(candidate[0]['content'].count('Reply with exactly one JSON object'), 1)
        self.assertNotIn('Reply with EXACTLY', candidate[0]['content'])

    def result(self, label, claim, *, status='recognised', sufficient=None, refs=None,
               vote='Proposal A'):
        text = 'Proposal A: the council recommends rejection. The levy is 5 francs.'
        doc = {'source': 'fixture.pdf', 'sha256': 'fixture', 'language': 'de',
               'pages': [{'page': 1, 'text': text}]}
        raw = {'label': label, 'reasoning': 'Deterministic contract fixture.',
               'vote_status': status,
               'vote_reference': {'passage_id': 'e1'} if status == 'recognised' else None,
               'evidence_status': sufficient or ('insufficient' if label == 'neutral' else 'sufficient'),
               'evidence_refs': refs if refs is not None else ([] if label == 'neutral' else [{'passage_id': 'e1'}])}
        judge = object.__new__(app.SubmissionJudge)
        judge.model, judge.context, judge.max_tokens = app.CSCS_MODEL, 32768, 512
        judge.base, judge.session = 'https://offline.invalid', Mock()
        judge.system_prompt = VOTE_IDENTITY_V1
        judge.session.post.return_value.json.return_value = {
            'model': app.CSCS_MODEL, 'choices': [{'message': {'content': json.dumps(raw)},
                                                'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 42, 'completion_tokens': 30}}
        request = {'id': 'fixture', 'claim': claim, 'booklet': 'fixture.pdf',
                   'vote': vote, 'evidence': 'full',
                   'pipeline_version': app.CANDIDATE_PIPELINE}
        with patch.dict(app.os.environ, {'LLM_TOKEN_PREFLIGHT': 'optional'}):
            result = app.classify(request, judge, booklet=doc)
        sent = judge.session.post.call_args.kwargs['json']['messages'][0]['content']
        self.assertIn(VOTE_IDENTITY_INSTRUCTIONS, sent)
        self.assertEqual(judge.session.post.call_count, 1)
        return result

    def test_unrelated_neutral_fixture_keeps_recognised_identity(self):
        result = self.result('neutral', 'A fourth week of holiday improves productivity.')
        self.assertEqual(result['vote_status'], 'recognised')
        output = app.submission_output(result)
        self.assertEqual(output['label'], 1)
        self.assertEqual(output['evidence'], [])

    def test_unrecognised_neutral_without_grounded_title_still_rejected(self):
        result = self.result('neutral', 'An unrelated claim.', status='unrecognised',
                             vote='Proposal B concerning school reform')
        self.assertEqual(result['error'], 'vote_unrecognised')
        with self.assertRaises(ValueError):
            app.submission_output(result)

    def test_valid_entailment_and_contradiction_fixtures_keep_citations(self):
        for label, claim, code in [('entailment', 'The council recommends rejection.', 0),
                                   ('contradiction', 'The council recommends acceptance.', 2)]:
            with self.subTest(label=label):
                output = app.submission_output(self.result(label, claim))
                self.assertEqual(output['label'], code)
                self.assertIn('recommends rejection', output['evidence'][0]['text'])

    def test_contradiction_without_sufficient_evidence_still_rejected(self):
        for sufficient, refs in [('insufficient', []), ('sufficient', [])]:
            with self.subTest(sufficient=sufficient):
                result = self.result('contradiction', 'The council recommends acceptance.',
                                     sufficient=sufficient, refs=refs)
                self.assertEqual(result['error'], 'insufficient_evidence')
                with self.assertRaises(ValueError):
                    app.submission_output(result)

    def test_neutral_with_claim_citations_still_rejected(self):
        result = self.result('neutral', 'An unrelated claim.', refs=[{'passage_id': 'e1'}])
        self.assertEqual(result['error'], 'invalid_neutral_evidence')

    def test_unknown_citation_still_rejected(self):
        result = self.result('entailment', 'The council recommends rejection.',
                             refs=[{'passage_id': 'e99'}])
        self.assertEqual(result['error'], 'unknown_evidence_reference')
