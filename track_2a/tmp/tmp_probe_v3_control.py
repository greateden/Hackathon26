"""Scratch negative control: is `_LEADING_LABEL_RE` really the cause?

Patches the module attribute back to the pre-fix `\\b` pattern and counts how
many of the four defect strings decode again. Proves the new tests in
tests/test_parse_nli.py are non-vacuous guards, not tautologies.

Run from src/:  python3 tmp_probe_v3_control.py
"""
import re

import nli_judge
from nli_judge import parse_nli_response as p

DEFECTS = ["neutral-ish", "entailment/neutral", "contradiction-like",
           "neutral/contradiction"]
KEEP = ["Neutral: insufficient evidence", "neutral.", "neutral " + "y" * 400]

fixed = nli_judge._LEADING_LABEL_RE
old = re.compile(r"\s*(entailment|neutral|contradiction)\b", re.IGNORECASE)

print("fixed rule decodes:", [(d, p(d)["label"]) for d in DEFECTS])
nli_judge._LEADING_LABEL_RE = old
back = [(d, p(d)["label"]) for d in DEFECTS]
print("old rule decodes:  ", back)
nli_judge._LEADING_LABEL_RE = fixed
print("restored, leaks under old rule:", sum(1 for _, lab in back if lab))
print("legit formats identical under both rules:",
      all(p(k)["label"] == "neutral" for k in KEEP))
assert nli_judge._LEADING_LABEL_RE is fixed
print("restored, defect decodings:", [(d, p(d)["label"]) for d in DEFECTS])