"""Offline regression checks for the NLI reply parser (no model, no server).

`parse_nli_response` is the only place where a model's free text becomes a
prediction, so two of its properties are load-bearing for every number the
eval harness reports:

  * strictness - a label is decoded ONLY from a JSON `label` field, a
    recoverable broken-JSON `label` pair, or a reply that STARTS with a bare
    label word. Prose that merely mentions a label word, castable junk like
    "1.5" or True, and fence-wrapped garbage never manufacture one;
  * representability - an unparsed reply comes back as
    {"label": None, "error": "unparseable_response"}, never as a bare string.
    `eval_nli.evaluate` reads `verdict["label"]`, so a bare-string return (or
    a keyword scan over the reasoning) would turn every unparsable reply into
    a wrong-but-counted prediction.

A label-shaped token only counts if it ENDS there (2026-10-11). The leading
matcher used to require only a word boundary, and `\b` matches at a hyphen or
a slash too, so "neutral-ish" decoded as neutral and "entailment/neutral" as
entailment: replies that refuse to choose were scored as verdicts. Compound
tokens are now pinned as NON-predictions, and the legitimate formats that sit
on the same boundary (a bare label, "neutral.", "Neutral: insufficient
evidence", fenced and JSON replies) are pinned as predictions - both
directions of the change are covered, so the fix cannot be quietly widened
into rejecting real answers.

Run from the repo root:
  PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from labels import CODE_TO_LABEL, code_to_label, label_to_code, normalise_label
from nli_judge import parse_nli_response

LABELS = ("entailment", "neutral", "contradiction")


def label_of(raw):
    """The prediction a raw reply decodes to (None = "no prediction")."""
    out = parse_nli_response(raw)
    assert isinstance(out, dict), (
        "parser must return a verdict dict, got %s: %r" % (type(out).__name__,
                                                            out))
    return out["label"]


class CodeDecodingTests(unittest.TestCase):
    """code_to_label maps the official codes; it is not a number parser."""

    def test_official_codes_decode_both_as_ints_and_strings(self):
        self.assertEqual(code_to_label(0), "entailment")
        self.assertEqual(code_to_label(1), "neutral")
        self.assertEqual(code_to_label(2), "contradiction")
        for code, name in (("0", "entailment"), ("1", "neutral"),
                           ("2", "contradiction")):
            self.assertEqual(code_to_label(code), name)

    def test_surrounding_whitespace_is_not_part_of_a_code(self):
        # the codes arrive from model text, where padding is noise, not data
        self.assertEqual(code_to_label(" 1 "), "neutral")
        self.assertEqual(code_to_label("2 "), "contradiction")
        self.assertEqual(code_to_label(" 0"), "entailment")

    def test_castable_junk_never_decodes(self):
        # 1.0 is the number a float-topped "1" would be; "01" is a padded
        # "1"; True == 1 in Python. None of them are official codes.
        junk = [1.0, 1.5, 2.0, 2.5, -1, 3, 10, True, False,
                "1.0", "1.5", "2.0", "01", "12", "code 2", "0x1",
                "nan", "", "   ", None]
        for value in junk:
            with self.subTest(value=value):
                self.assertIsNone(code_to_label(value))

    def test_label_names_are_not_codes(self):
        for name in LABELS:
            self.assertIsNone(code_to_label(name))

    def test_mapping_and_round_trip(self):
        self.assertEqual(CODE_TO_LABEL,
                         {0: "entailment", 1: "neutral", 2: "contradiction"})
        for code, name in CODE_TO_LABEL.items():
            self.assertEqual(label_to_code(name), code)
            self.assertEqual(label_to_code(name.lower()), code)


class NormaliseLabelTests(unittest.TestCase):
    """normalise_label is the boundary between model text and a class."""

    def test_accepts_names_and_codes_in_any_case(self):
        for raw in ("entailment", "NEUTRAL", " Contradiction ", "1", 0, "2",
                    "0", 2, "1"):
            with self.subTest(raw=raw):
                self.assertIn(normalise_label(raw), LABELS)

    def test_rejects_near_misses_and_non_labels(self):
        for raw in ("neutral-ish", "E", "entailed", "maybe neutral", 1.5,
                    True, None, "", " "):
            with self.subTest(raw=raw):
                self.assertIsNone(normalise_label(raw))


class VerdictShapeTests(unittest.TestCase):
    """The return type is part of the contract, not an implementation detail.

    CORPUS is a spread of realistic replies; the shape assertions below run
    over all of them, so a new reply form cannot slip a bare string (or a
    label that is not one of the three classes) past the harness.
    """

    CORPUS = [
        "entailment",
        "neutral",
        "contradiction",
        "neutral " + "y" * 400,
        "z" * 400,
        "The claim is entailed.",
        "**Answer:** Contradiction",
        "Label: neutral",
        "neutral-ish",
        "entailment/neutral",
        "contradiction-like",
        "neutral/contradiction",
        "Neutral: insufficient evidence",
        '{"label": "neutral"}',
        '{"label": 0}',
        '{"label": "neutral", "evidence_snippet": "some snippet"}',
        '{"reasoning": "it says neutral", "label": "contradiction"}',
        '{"label": "neutral"',
        '{"label": "5"}',
        '{"label": "1.5"}',
        '{"label": true}',
        '{"label": null}',
        '{"reasoning": "no label here"}',
        'no json here {"label": "neutral"}',
        '{"label": "entailment"} trailing prose',
        '```json\n{"label": "neutral"}\n```',
        "```\nneutral\n```",
        "```\nneutral",
        "   ```json\n{\"label\": \"neutral\"}\n```   ",
        "```",
        "",
    ]

    def test_every_reply_decodes_to_a_verdict_dict(self):
        for raw in self.CORPUS:
            with self.subTest(raw=raw[:40]):
                out = parse_nli_response(raw)
                self.assertIsInstance(out, dict)
                self.assertIn("label", out)
                self.assertTrue(out["label"] is None
                                or out["label"] in LABELS)

    def test_a_label_and_an_error_are_never_both_set(self):
        for raw in self.CORPUS:
            with self.subTest(raw=raw[:40]):
                out = parse_nli_response(raw)
                self.assertFalse("error" in out and out.get("label"))

    def test_unparsable_replies_are_errors_not_a_defaulted_neutral(self):
        # the invariant behind AGENTS.md: no keyword-search fallback over free
        # text and no silent "neutral" default. An unparsable reply has to
        # stay visible as an error in the summary, or accuracy becomes fiction.
        unparsable = [r for r in self.CORPUS if label_of(r) is None]
        self.assertGreater(len(unparsable), 5)
        for raw in unparsable:
            with self.subTest(raw=raw[:40]):
                out = parse_nli_response(raw)
                self.assertEqual(out["error"], "unparseable_response")
                self.assertIn("Unparseable response: ", out["reasoning"])

    def test_prose_mentioning_a_label_is_not_a_label(self):
        for raw in ("The claim is entailed.", "**Answer:** Contradiction",
                    "Label: neutral", "maybe neutral", "it says neutral"):
            with self.subTest(raw=raw):
                self.assertIsNone(label_of(raw))

    def test_long_reasoning_is_truncated_but_still_a_verdict(self):
        out = parse_nli_response("neutral " + "y" * 400)
        self.assertEqual(out["label"], "neutral")
        self.assertEqual(len(out["reasoning"]), 200)
        self.assertNotIn("error", out)
        bad = parse_nli_response("z" * 400)
        self.assertTrue(bad["reasoning"].startswith("Unparseable response: "))
        self.assertEqual(len(bad["reasoning"]), 142)  # marker + first 120


class JsonDecodingTests(unittest.TestCase):
    """A JSON reply is parsed as data, not scanned for label-shaped words."""

    def test_invalid_structured_labels_cannot_be_rescued(self):
        for raw in ('{"label":null,"nested":{"label":"neutral"}}',
                    '{"nested":{"label":"neutral"}}',
                    '{"label":"neutral","label":null}',
                    '{"label":1/2,', '{"label":"neutral"ish,'):
            with self.subTest(raw=raw):
                self.assertIsNone(label_of(raw))

    def test_label_taken_from_the_json_field(self):
        cases = {
            '{"label": "neutral"}': "neutral",
            '{"label": "contradiction"}': "contradiction",
            '{"label": "NEUTRAL"}': "neutral",
            '{"label": 0}': "entailment",
            '{"label": 1}': "neutral",
            '{"label": 2}': "contradiction",
            '{"label": "2"}': "contradiction",
        }
        for raw, want in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(label_of(raw), want)

    def test_key_order_and_trailing_prose_do_not_hide_the_label(self):
        # the label travels in its own field, so where the field sits is
        # irrelevant - only its absence is
        self.assertEqual(label_of('{"reasoning": "it says neutral", '
                                  '"label": "contradiction"}'),
                         "contradiction")
        self.assertEqual(label_of('{"label": "entailment"} trailing prose'),
                         "entailment")
        self.assertEqual(label_of('no json here {"label": "neutral"}'),
                         "neutral")

    def test_other_keys_pass_through_untouched(self):
        out = parse_nli_response('{"label": 1, "evidence_snippet": "snip"}')
        self.assertEqual(out["label"], "neutral")
        self.assertEqual(out["evidence_snippet"], "snip")
        self.assertNotIn("reasoning", out)

    def test_a_truncated_json_label_is_recovered(self):
        # a streamed reply that lost its closing brace is still data
        self.assertEqual(label_of('{"label": "neutral"'), "neutral")

    def test_a_non_official_label_in_json_is_not_rescued(self):
        for raw in ('{"label": "5"}', '{"label": "1.5"}', '{"label": 1.5}',
                    '{"label": "neutral-ish"}', '{"label": true}',
                    '{"label": null}', '{"reasoning": "no label here"}'):
            with self.subTest(raw=raw):
                out = parse_nli_response(raw)
                self.assertIsNone(out["label"])
                self.assertEqual(out["error"], "unparseable_response")


class FenceAndLeadingLabelTests(unittest.TestCase):
    """Fence unwrapping, and the leading-label rule in both directions."""

    def test_fenced_replies_are_unwrapped(self):
        for raw in ('```json\n{"label": "neutral"}\n```',
                    "```\nneutral\n```",
                    "```\nneutral",  # unclosed fence
                    '   ```json\n{"label": "neutral"}\n```   '):
            with self.subTest(raw=raw):
                self.assertEqual(label_of(raw), "neutral")

    def test_a_bare_label_answer_decodes(self):
        for raw, want in (("entailment", "entailment"),
                          ("neutral", "neutral"),
                          ("contradiction", "contradiction"),
                          ("NEUTRAL", "neutral"),
                          ("  contradiction  ", "contradiction"),
                          ("neutral.", "neutral"),
                          ("Contradiction.", "contradiction"),
                          ("Neutral because the booklet says otherwise.",
                           "neutral"),
                          ("neutral\n\nsome reasoning", "neutral")):
            with self.subTest(raw=raw):
                self.assertEqual(label_of(raw), want)

    def test_a_joined_label_token_is_not_a_verdict(self):
        # Regression guard, added with the v3 parser fix (2026-10-11). Each of
        # these names a label, but only as part of a compound token that
        # refuses to commit: an "-ish"/"-like" hedge, or two labels joined by
        # "/", "~" or "|". The old `\b` boundary matched at the joiner, so the
        # leading word won and a refusal was scored against the gold label.
        # None of them may decode, and each must stay visible as an error.
        for raw in ("neutral-ish", "entailment/neutral",
                    "contradiction-like", "neutral/contradiction",
                    "entailment~neutral", "neutral|contradiction",
                    "neutral-ish: hard to say", "contradiction-like wording",
                    "neutral-ish because the booklet is ambiguous"):
            with self.subTest(raw=raw):
                out = parse_nli_response(raw)
                self.assertIsNone(out["label"])
                self.assertEqual(out["error"], "unparseable_response")

    def test_a_delimited_explanation_is_still_a_verdict(self):
        # The other half of the fix. The boundary that had to stop matching at
        # a joiner must keep matching after a real delimiter, or legitimate
        # "label + explanation" replies start reporting as errors and the
        # measurement quietly loses real answers instead of fabricating them.
        for raw, want in (("Neutral: insufficient evidence", "neutral"),
                          ("neutral: the booklet is silent on this", "neutral"),
                          ("Contradiction - the booklet denies it",
                           "contradiction"),
                          ("entailment; the text entails it", "entailment"),
                          ("neutral, the text is silent", "neutral"),
                          ("neutral\nthe text is silent", "neutral"),
                          ("entailment (direct)", "entailment")):
            with self.subTest(raw=raw):
                self.assertEqual(label_of(raw), want)

    def test_a_fenced_non_label_stays_unparsable(self):
        for raw in ("```",
                    '```json\n{"label": "1.5"}\n```',
                    "```\nThe claim is entailed.\n```"):
            with self.subTest(raw=raw):
                self.assertIsNone(label_of(raw))


if __name__ == "__main__":
    unittest.main(verbosity=2)
