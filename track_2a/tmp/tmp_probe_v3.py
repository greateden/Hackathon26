"""Scratch check for the v3 leading-label rule (not part of the test suite).

Run from src/:  python3 tmp_probe_v3.py
"""
from nli_judge import parse_nli_response as p

MUST_BE_NONE = ["neutral-ish", "entailment/neutral", "contradiction-like",
                "neutral/contradiction"]

MUST_KEEP = {
    "Neutral: insufficient evidence": "neutral",
    "neutral": "neutral",
    "contradiction": "contradiction",
    "entailment": "entailment",
    "NEUTRAL": "neutral",
    "  contradiction  ": "contradiction",
    "neutral.": "neutral",
    "Contradiction.": "contradiction",
    "Neutral because the booklet says otherwise.": "neutral",
    "neutral\n\nsome reasoning": "neutral",
    "neutral " + "y" * 400: "neutral",
    "Contradiction - the booklet denies it": "contradiction",
    "entailment; the text entails it": "entailment",
    "neutral, the text is silent": "neutral",
    "entailment (direct)": "entailment",
    '{"label": "neutral"}': "neutral",
    '{"label": 1}': "neutral",
    '{"label": "contradiction"} trailing': "contradiction",
    "```\nneutral\n```": "neutral",
    # unchanged behaviour: prose that merely mentions a label stays unparsable
    "Label: neutral": None,
    "The claim is entailed.": None,
    "**Answer:** Contradiction": None,
    "maybe neutral": None,
    "it says neutral": None,
    '{"label": "neutral-ish"}': None,
}

bad = [(repr(s), p(s)) for s in MUST_BE_NONE if p(s)["label"] is not None]
bad += [(repr(s), p(s)["label"], want) for s, want in MUST_KEEP.items()
        if p(s)["label"] != want]
for row in bad:
    print("MISMATCH:", row)
print("leaks/mismatches:", len(bad))
print("defect reply ->", p("neutral/contradiction"))