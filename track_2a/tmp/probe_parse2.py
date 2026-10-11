import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from nli_judge import parse_nli_response as p

cases = [
    '{"label": "contradiction", "snippet": "unterminated',
    '{"label": 1',
    '{"label": 1.5',
    '{"label": "neutral-ish"',
    'prefix text {"label": "neutral"',
    'Blabla {"label": "neutral"} more text',
    '{"label": null}',
    '{"label": "neutral"}\nSome trailing prose',
    'The booklet says X. {"label": "contradiction"}',
    '{"label": "CONTRADICTION", "reasoning": "r"}',
    '{"reasoning": "no label here", "evidence_snippet": "z"}',
    '{"label": 0}',
    '{"label": 3}',
    '{"label": true}',
]
for c in cases:
    print(repr(c), '->', p(c))
