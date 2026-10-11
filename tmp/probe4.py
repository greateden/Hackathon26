"""Second probe: the edge cases the pin-down test wants to assert exactly."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from labels import LABEL_PARSE_VERSION, code_to_label as c2l, label_to_code as l2c
from nli_judge import parse_nli_response as p

print("v", LABEL_PARSE_VERSION)
CASES = [
    "",
    "   ",
    "maybe",
    "The claim is entailed.",
    '{"label":"entailment","reasoning":"The claim mentions nuclear energy."}',
    '{"label":"neutral","reasoning":"The claim mentions nuclear energy."}',
    "The claim mentions nuclear energy. " + '{"label":"neutral"}',
    "```json\n" + '{"label":"neutral","reasoning":"x"}' + "\n```",
    "neutral. The claim is unrelated.",
    "This claim is not well formed. " + '{"label":"contradiction"}' + " maybe",
    "Label: neutral",
    "  contradiction  ",
    '{"label": "neutral"}\n{"label": "contradiction"}',
    '{"a": 1, "label": "neutral"}',
]
for x in CASES:
    print(repr(x), "->", repr(p(x)))

print("boundary:", [(v, c2l(v)) for v in
      [" 1 ", "code 2", 1.0, "1.0", "01", "3", -1, 9, None, "", "neutral",
       0, "0", "2", 2, True]])
print("l2c", l2c(None), l2c("neutral"), l2c(" Neutral "), l2c("foo"))
r = p("x" * 400)
print("long reasoning len", len(r["reasoning"]), repr(r["reasoning"][-8:]))
