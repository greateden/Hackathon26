"""Third probe: the remaining inputs the pin-down test wants to assert.

Run from the repo root:
  PYTHONPATH=src python3 tmp/probe5.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from labels import code_to_label, normalise_label
from nli_judge import parse_nli_response as p

CASES = [
    # bare letters / codes
    "E", "e", "N", "C", "c", "0", "1", "2", " 1 ", "code 2", "1.5", "0.5",
    # label words with trailing junk
    "neutral-ish", "entailment/neutral", "contradiction-ish, hard to say",
    "Contradiction: the text denies it", "Neutral\n", "Entailment.",
    "  contradiction  ",
    # label word mentioned later in prose (must NOT decode)
    "The claim is entailed.", "Let me think. The claim is entailed, so neutral.",
    "I think this is contradiction, but entailment is also possible.",
    "Reason: the text mentions no such thing. Therefore entailment.",
    "Maybe entailment or neutral?", "The answer is not entailment; it is neutral.",
    "Label: neutral", "label: neutral", "**Answer:** Contradiction",
    "Answer: contradiction", "Verdict: CONTRADICTION", "maybe", "yes",
    "The claim is unclear.",
    # JSON-shaped replies
    '{"label": "neutral"}', '{"label": "neutral"}\n{"label": "contradiction"}',
    '{"a": 1, "label": "neutral"}', '{"label": 1}', '{"label": 1.5}',
    '{"label": true}', '{"label": null}', '{"label": ""}',
    '{"label": "1"}', '{"label": "2"}', '{"label": "1.5"}',
    '{"label": "NEUTRAL"}', '{"label": " neutral "}', '{"label": "neutral-ish"}',
    '{"label": "neutral"',  # broken JSON, recoverable
    '{"label": "neutral"',
    'no json here {"label": "neutral"}',
    'This claim is not well formed. {"label":"contradiction"} maybe',
    '```json\n{"label":"neutral","reasoning":"x"}\n```',
    '```json\nThe claim is entailed.\n```',
    '```json\nentailment\n```',
    "The claim mentions nuclear energy. " + '{"label":"neutral"}',
]
for x in CASES:
    print(repr(x), "->", repr(p(x)))

print("--- non-str inputs (does the parser survive them?) ---")
for x in [None, True, False, 1, 0.0, ["entailment"], b"neutral", {"label": 1}]:
    try:
        print(repr(x), "->", repr(p(x)))
    except Exception as e:
        print(repr(x), "-> RAISED", type(e).__name__, e)

print("--- normalise_label accepts names AND codes ---")
print([(v, normalise_label(v)) for v in
       ["neutral", "NEUTRAL", " neutral ", "1", 1, 1.0, True, "1.5", "E", ""]])

print("--- code_to_label: whitespace-tolerant, strict otherwise ---")
print([(v, code_to_label(v)) for v in [" 1 ", "1 ", " 2", "neutral"]])
