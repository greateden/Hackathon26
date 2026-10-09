"""Deterministic unit checks for the label mapping and judge plumbing.

No models are loaded and no corpus is needed; safe for routine runs.
Usage:  python3 test_judge.py   (from src/)"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from labels import (label_to_code, code_to_label, normalise_label,
                    LABEL_TO_CODE, CODE_TO_LABEL)
from nli_judge import parse_nli_response, format_evidence

FAILURES = []


def check(cond, msg):
    status = "ok" if cond else "FAIL"
    print(f"[{status}] {msg}")
    if not cond:
        FAILURES.append(msg)


# --- official label mapping -------------------------------------------------
check(label_to_code("entailment") == 0, "entailment -> 0")
check(label_to_code("neutral") == 1, "neutral -> 1")
check(label_to_code("contradiction") == 2, "contradiction -> 2")
check(label_to_code(None) is None, "None label -> None (no silent neutral)")
check(label_to_code("garbage") is None, "unknown label -> None")
check(code_to_label(0) == "entailment", "code 0 -> entailment")
check(code_to_label("1") == "neutral", "code '1' (str) -> neutral")
check(code_to_label(9) is None, "invalid code 9 -> None")
check(normalise_label("Contradiction ") == "contradiction",
      "normalise: case/whitespace tolerated")
check(normalise_label(2) == "contradiction", "normalise: int code")
check(normalise_label(None) is None, "normalise: None")
check(set(LABEL_TO_CODE.values()) == set(CODE_TO_LABEL.keys()) == {0, 1, 2},
      "mapping round-trip covers 0/1/2")

# --- response parsing ---------------------------------------------------------
r = parse_nli_response('{"label": "contradiction", "reasoning": "r", '
                       '"evidence_snippet": "e"}')
check(r["label"] == "contradiction" and not r.get("error"),
      "valid JSON parses")

r = parse_nli_response('```json\n{"label": "0", "reasoning": "x", '
                       '"evidence_snippet": "y"}\n```')
check(r["label"] == "entailment" and r.get("evidence_snippet") == "y",
      "fenced JSON with numeric code '0' normalises to entailment")

r = parse_nli_response('{"label": "neutral", "reasoning": "trunc')
check(r["label"] == "neutral", "truncated JSON recovers quoted label")

r = parse_nli_response("The evidence discusses the contradiction between "
                       "canton and federation; cannot decide.")
check(r["label"] is None and r.get("error") == "unparseable_response",
      "prose mentioning a label word mid-sentence is an error, "
      "not a prediction (regression guard for the old keyword fallback)")

r = parse_nli_response('{"label": "maybe", "reasoning": "?"}')
check(r["label"] is None and r.get("error"), "invalid label value -> error")

r = parse_nli_response("")
check(r["label"] is None and r.get("error"), "empty response -> error")

r = parse_nli_response("neutral")
check(r["label"] == "neutral", "bare leading label word accepted")

# --- evidence formatting ------------------------------------------------------
check(format_evidence([]) == "(No relevant passages found.)",
      "no passages -> explicit empty-evidence marker")

long_p = [{"id": "de_2007_001", "lang": "de", "text": "x" * 1500},
          {"id": "fr_2007_001", "lang": "fr", "text": "y" * 1500}]
ev = format_evidence(long_p, max_chars=2000)
check("x" * 1500 in ev and "y" * 1500 not in ev,
      "evidence block respects max_chars cap")

print()
if FAILURES:
    print(f"{len(FAILURES)} FAILURES")
    sys.exit(1)
print("all judge/label checks passed")
