import sys
sys.path.insert(0, "src")
from labels import code_to_label, normalise_label, label_to_code
from nli_judge import parse_nli_response as p

print("-- code_to_label strict --")
for v in [" 1 ", "2 ", " 0", 1.0, 1.5, 2.0, 2.5, -1, 3, 10, "1.0", "1.5",
          "01", "12", "code 2", "0x1", "nan", None, "", "  ", "neutral"]:
    print(repr(v), "->", code_to_label(v))

print("-- label_to_code --")
for v in ["neutral", "NEUTRAL ", None, "nope", 1, "entailment"]:
    print(repr(v), "->", label_to_code(v))

print("-- normalise_label --")
for v in ["neutral-ish", "E", "entailed", 1.5, True, None, "1", "2", "0"]:
    print(repr(v), "->", normalise_label(v))

print("-- parse --")
cases = [
 'Label: neutral',
 '**Answer:** Contradiction',
 'The claim is entailed.',
 'neutral.',
 'Contradiction.',
 'Neutral because the text says otherwise.',
 'entailment/neutral',
 'neutral-ish',
 'neutral' + ' x' * 200,
 '{"label": "neutral-ish"}',
 '{"label": true}',
 '{"label": 5}',
 '{"label": "5"}',
 '{"label": null}',
 '{"label": 1, "evidence_snippet": "some snippet"}',
 '{"label":"contradiction","evidence_snippet":"x"}',
 '```\nneutral\n```',
 '```json\n{"label":"neutral"}\n```',
 '```\nneutral',
 '   ```json\n{"label":"neutral"}\n```   ',
 'neutral\n\nmore reasoning',
 'contradiction',
 '{"label": "entailment"} trailing prose',
 'NEUTRAL',
 '  contradiction  ',
 '{"label": 2}',
]
for c in cases:
    out = p(c)
    print(repr(c[:58]), "->", repr(out)[:190])
