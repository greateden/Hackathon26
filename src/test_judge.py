"""Deterministic unit checks for the label mapping and judge plumbing.

No models are loaded and no corpus is needed; safe for routine runs.
Usage:  python3 test_judge.py   (from src/)"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from labels import (label_to_code, code_to_label, normalise_label,
                    LABEL_TO_CODE, CODE_TO_LABEL)
from nli_judge import (parse_nli_response, format_evidence, build_chat,
                       get_prompt_config, PROMPT_CONFIGS, SYSTEM_PROMPT,
                       STRICT_SYSTEM_PROMPT)

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

# 'fill' style (ablation config "select"): long chunks are truncated to fit,
# never silently dropped, and the hard cap still holds INCLUDING join overhead
ev_fill = format_evidence(long_p, max_chars=2000, style="fill")
check("y" * 1500 not in ev_fill and "y" * 100 in ev_fill
      and len(ev_fill) <= 2000,
      "fill style: second passage truncated to fit, cap honoured")

# --- prompt-config registry ---------------------------------------------------
check(set(PROMPT_CONFIGS) == {"baseline", "t0", "strict", "select"},
      "registry has exactly baseline/t0/strict/select")
_b = get_prompt_config("baseline")
check(_b["temperature"] == 0.1 and _b["max_tokens"] == 400
      and _b["evidence"] == "drop" and not _b["window"],
      "baseline config keeps the 2026-10-10 dev-run settings unchanged")
check(all(get_prompt_config(c)["temperature"] == 0.0
          for c in ("t0", "strict", "select")),
      "ablation arms run at temperature 0")
try:
    get_prompt_config("nope")
    check(False, "unknown prompt-config name rejected")
except ValueError as e:
    check("nope" in str(e) and "baseline" in str(e),
          "unknown prompt-config name rejected with valid list")

_claim = "The Federal Council rejects the nuclear phase-out initiative."
_p = [{"id": "x1", "lang": "de", "text": "Der Bundesrat lehnt sie ab."}]
sys_b, user_b = build_chat(_b, _claim, _p)
check(sys_b == SYSTEM_PROMPT
      and user_b.endswith("Reply with JSON only.")
      and "nuclear phase-out" in user_b,
      "baseline build_chat renders the original prompt verbatim")
sys_s, user_s = build_chat(get_prompt_config("strict"), _claim, _p)
check(sys_s == STRICT_SYSTEM_PROMPT
      and "Sharing the same topic is NOT entailment" in sys_s
      and "never contradiction" in sys_s
      and user_s == user_b,
      "strict config swaps only the system prompt (single-factor ablation)")

# --- claim-lexical evidence window (select config, oracle mode) --------------
from eval_nli import select_window

_head = "Die Sicherheitslage in Europa hat sich verschlechtert. " * 120
_tail = ("Die Kommission beantragt daher den Gegenvorschlag. " * 3
         + "Der Bundesrat lehnt den Atomausstieg explizit ab. " * 2)
_long = _head + "\n\n" + _tail
_window = select_window(_long, "The government rejects the nuclear phase-out "
                        "(Atomausstieg).", 1900)
check("Atomausstieg" in _long and "Atomausstieg" not in _long[:1900],
      "fixture: decisive marker only beyond the head-truncation boundary")
check("Atomausstieg" in _window,
      "select_window reaches the tail marker the head cut would drop")
check(len(_window) <= 1900 and len(select_window(_long, "quantum teleport",
                                                 1900)) == 1900,
      "select_window: cap honoured; no-overlap falls back to the head")
check(select_window("short text", "whatever claim", 1900) == "short text",
      "short evidence passes through untouched")

# --- OpenAI-compatible endpoint judge --------------------------------------
# Offline, hermetic checks (no server needed): the judge must REFUSE to
# build when the endpoint is unreachable (no silent lexical fallback) and
# must tolerate both model-listing shapes.
import importlib.util
if importlib.util.find_spec("requests"):
    from nli_judge import OpenAICompatJudge
    try:
        OpenAICompatJudge(base_url="http://127.0.0.1:9")
        check(False, "openai judge refuses an unreachable endpoint")
    except RuntimeError as e:
        check("not reachable" in str(e),
              "openai judge refuses an unreachable endpoint "
              "(no silent lexical fallback)")
    check(OpenAICompatJudge._served_model_ids(
              {"data": [{"id": "m1"}]}) == ["m1"],
          "model-listing parse: OpenAI data[].id shape")
    check(OpenAICompatJudge._served_model_ids(["m2"]) == ["m2"],
          "model-listing parse: bare id list shape")
else:
    print("[skip] requests not installed: openai-judge checks skipped")

print()
if FAILURES:
    print(f"{len(FAILURES)} FAILURES")
    sys.exit(1)
print("all judge/label checks passed")
