import sys
sys.path.insert(0, '/Users/liyitian/Documents/Hackathon26/src')
from nli_judge import parse_nli_response as p

cases = [
    'entailment', 'neutral', 'contradiction', 'E', 'e', 'N', 'c',
    '  CONTRADICTION ', 'Entailment.', 'Neutral\n', '0', '1', '2',
    'Contradiction: the text denies it',
    'NEUTRAL\nBecause the text is unrelated',
    'neutral-ish', 'contradiction-ish', 'entailment/neutral',
    'Maybe entailment or neutral?',
    'Let me think. The claim is entailed, so neutral.',
    'I think this is contradiction, but entailment is also possible.',
    'Reason: the text mentions no such thing. Therefore entailment.',
    'The answer is not entailment; it is neutral.',
    'label: contradiction',
    'The answer is contradiction.',
    'neutral because blah',
    '{"label": "entailment"}',
    '{"label": 2}',
    '```json\n{"label": "neutral"}\n```',
    '{"label": "neutral", "reasoning": "x"}',
    '{"label": 1.5, "reasoning": "x"}',
    '{"label": "neutral-ish"}',
    '{"label": "Neutral"}',
    'garbage {"foo": 1}',
    'maybe', 'yes', '', '   ', '1.5', '0.0', 'True', '"neutral"',
    'Neutral.', 'contradiction', 'ENTAILMENT!',
]
for c in cases:
    print(repr(c), '->', p(c))
