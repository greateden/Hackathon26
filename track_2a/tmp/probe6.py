import sys
sys.path.insert(0, "src")
from labels import code_to_label, normalise_label, label_to_code
from nli_judge import parse_nli_response as p

print("-- code_to_label --")
for v in [" 1 ", "2 ", " 0", 1.0, 1.5, 2.0, 2.5, -1, 3, 10, "1.0", "1.5",
          "01", "12", "code 2", "0x1", "nan", None, "", "  ", "neutral"]:
    print(repr(v), "->", code_to_label(v))

print("-- normalise_label --")
for v in ["neutral", "NEUTRAL", " neutral ", "Contradiction", "entailment",
          1, 0, 2, "1", "2", "neutral-ish", "E", "", " ", 1.5, True, None,
          "entailed"]:
    print(repr(v), "->", normalise_label(v))

print("-- label_to_code --")
for v in ["neutral", "NEUTRAL ", None, "nope", 1]:
    print(repr(v), "->", label_to_code(v))

print("-- parse extras --")
cases = [
    '{"label": 0}',
    '{"label": "neutral"',
    '{"label": "1.5"',
    '{"label":"neutral","reasoning":"because neutral"}',
    '{"reasoning": "it says neutral", "label": "contradiction"}',
    '```\nneutral\n```',
    '```json\n{"label":"neutral"}\n```',
    'neutral' + ' x' * 200,
    'neutral',
    '{"label": "contradiction"}',
    'no json here {"label": "neutral"}',
    'Label: neutral',
    '**Answer:** Contradiction',
    'Verdict: CONTRADICTION',
    'neutral-ish',
    'entailment/neutral',
    'The claim is entailed.',
]
for c in cases:
    out = p(c)
    print(repr(c[:55]), "->", repr(out)[:150])

print("-- long reasoning cap --")
out = p("neutral " + "y" * 400)
print(len(out["reasoning"]), out.get("error"))
out = p("z" * 400)
print(len(out["reasoning"]), repr(out["reasoning"][:40]), out["evidence_snippet"])
