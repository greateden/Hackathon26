"""Ground-truth probe: what does parse_nli_response actually return?

Prints repr(result) for every candidate input so the assertions written into
tests/test_parse_nli.py match reality rather than the intended policy.
Run from repo root: PYTHONPATH=src python3 tmp/probe_parse3.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nli_judge import parse_nli_response  # noqa: E402

GROUPS = [
    ("JSON answers (exact codes and names)", [
        '{"label": "contradiction", "reasoning": "x"}',
        '{"label": "entailment"}',
        '{"label": "neutral"}',
        '{"label": "NEUTRAL"}',
        '{"label": " neutral "}',
        '{"label": 0}',
        '{"label": 1}',
        '{"label": 2}',
        '{"label": "0"}',
        '{"label": "2"}',
        '{"label": 1.5}',
        '{"label": true}',
        '{"label": null}',
        '{"label": ""}',
        '{"label": "foo"}',
        '{"label": "neutral-ish"}',
        '{"label": "1.5"}',
        '{"label": "entailment"} and also contradiction',
    ]),
    ("Broken JSON (recovery channel)", [
        '{"label": "entailment"',
        '{"label":"contradiction","reasoning":"because"}',
        '{"a": 1} garbage {"label": "neutral"}',
        '{"label": "neutral" ',
    ]),
    ("Fenced code blocks", [
        '```json\n{"label": "entailment"}\n```',
        '```\n{"label": "contradiction", "reasoning": "because"}\n```',
        '```json\nentailment\n```',
        '```json\nThe claim is entailed.\n```',
    ]),
    ("Answer-first (leading label word)", [
        'entailment',
        'neutral',
        'contradiction',
        'Entailment.',
        'CONTRADICTION',
        ' Neutral\n',
        'Contradiction: the text denies it',
        'contradiction - the text denies it',
        'neutral because the text is unrelated',
        'Entailment (because the source confirms it)',
    ]),
    ("-ish suffixes (leak check)", [
        'neutral-ish',
        'contradiction-ish, hard to say',
        'entailment-ish',
    ]),
    ("Prose that merely mentions labels (must stay unparsed)", [
        'The claim is entailed, so neutral.',
        'Maybe entailment or neutral?',
        'Reason: no mention. Therefore entailment.',
        'The answer is not entailment; it is neutral.',
        'I think this is contradiction, but entailment is also possible.',
        'Label: neutral',
        'label: neutral',
        '**Answer:** Contradiction',
        'Answer: contradiction',
        'Verdict: CONTRADICTION',
        '   ',
        'true',
    ]),
    ("Bare letters / codes (no such channel exists)", [
        '0', '1', '2', '2. Contradiction', 'CODE 2', 'C', 'c', 'E', 'N',
    ]),
]

NON_STR = [None, 1, True, 0.0, ["entailment"]]

for title, cases in GROUPS:
    print(f"\n=== {title} ===")
    for c in cases:
        print(f"{c!r:58} -> {parse_nli_response(c)!r}")

print("\n=== non-str input (parser assumes str) ===")
for c in NON_STR:
    try:
        out = parse_nli_response(c)
    except Exception as e:
        out = f"{type(e).__name__}: {e}"
    print(f"{c!r:58} -> {out!r}")
