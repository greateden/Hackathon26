"""Offline probe: current parser behaviour + impact on recorded runs.

Temporary diagnostic (tmp/, untracked). Run:  python3 tmp/probe_parser.py
"""
import glob
import json
import os
import sys

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
sys.path.insert(0, SRC)
from nli_judge import parse_nli_response as p  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

CASES = [
    "Neutral is the correct label because the booklet does not take a position.",
    '{"label": "contradiction", "label": "entailment"}',
    '{"label":"neutral","error":"rate_limit_exceeded"}',
    "Contradiction. The booklet explicitly rejects the claim.",
    "Entailment",
    "neutral",
    "The evidence is about the same topic but does not decide: neutral.",
    '```json\n{"label": "2", "reasoning": "x", "evidence_snippet": "y"}\n```',
    '{"label": "neutral"}\n\nneutral',
]

print("--- current behaviour on audit reproducer strings ---")
for c in CASES:
    r = p(c)
    print(f"  {c[:58]!r:62} -> label={r.get('label')!r} error={r.get('error')!r}")

print("\n--- recorded-run scan (does a stricter parser change any recorded pred?) ---")
files = sorted(glob.glob(os.path.join(DATA, "eval_results_*.json")))
summary = os.path.join(DATA, "ablation_20261010_122340_openai.json")
if os.path.exists(summary):
    s = json.loads(open(summary).read())
    for r in s.get("runs", []):
        f = os.path.join(DATA, os.path.basename(r["file"]))
        if os.path.exists(f) and f not in files:
            files.append(f)

raw_keys = ("raw", "response", "raw_response", "text", "output")
total_items = 0
files_with_raw = 0
for f in files:
    payload = json.loads(open(f).read())
    items = payload.get("items", [])
    total_items += len(items)
    if items:
        print(f"  {os.path.basename(f)}: n={len(items)} keys={sorted(items[0])}")
        if any(k in items[0] for k in raw_keys):
            files_with_raw += 1
    meta = payload.get("meta", {})
    print(f"     meta: n_items={meta.get('n_items')} limit={meta.get('limit')} "
          f"parse_v={meta.get('label_parse_version')} "
          f"metrics_v={meta.get('metrics_version')}")
print(f"  files={len(files)} items={total_items} files_with_raw_text={files_with_raw}")
