"""Official HackApertus Track 2A label mapping (machine-readable part).

The official challenge labels are numeric codes:

    0 = entailment
    1 = neutral      ("Unrelated / Neutral" in the dataset README)
    2 = contradiction

Verified 2026-10-09 against the README of the official evaluation dataset
OSTswiss/MNLIoverSwissVotingBooklets and against manual inspection of two
sample items per class. Internal pipeline code keeps the label *names*
(see config.NLI_LABELS); conversion happens only at IO boundaries (result
files, evaluation scoring) via the helpers here, so the numeric mapping is
defined exactly once.
"""

LABEL_TO_CODE = {"entailment": 0, "neutral": 1, "contradiction": 2}
CODE_TO_LABEL = {code: name for name, code in LABEL_TO_CODE.items()}

# Parser policy version (2026-10-10 remediation pass). v1 accepted anything
# int() would cast, so 1.5 / True / "1.0" silently decoded as a label.
# v2 is strict: exact int 0/1/2, exact digit strings "0"/"1"/"2", or exact
# label names (case/whitespace tolerant). Everything else -> None. Bump this
# constant together with any policy change, and record it in eval metadata so
# historical v1 runs stay attributable.
# v2.1 (2026-10-10 audit fix): the broken-JSON *recovery* regex in
# nli_judge used to prefix-match ("1" inside "1.5", "neutral" inside
# "neutral-ish"), so the recovery path leaked non-strict values. Recovery
# now captures the complete value token and runs it through the same strict
# rules. Runs recorded as "label-parse-v2-strict" still contain that leak;
# only v2.1-onward runs are fully strict.
# v3 (2026-10-11): closes the OTHER leak, the plain-text one. The
# leading-label rule's `\b` boundary also matched at "-", "/", "~" and "|",
# so a reply that refused to choose ("neutral-ish", "entailment/neutral",
# "contradiction-like", "neutral/contradiction") decoded as its leading word
# and was scored against the gold label - a JSON reply had to carry a strict
# label, but a plain-text refusal never reached that check. A leading label
# now counts only when its token ends there. Dev runs recorded before this
# bump (report §4.2/§4.3, under v2.1) contain those refusals-as-predictions,
# so they are not comparable item-for-item with v3 runs.
# v3.1 (2026-10-12): valid JSON with no valid top-level label cannot enter
# recovery; recovered values must end at a JSON delimiter (not e.g. 1/2).
# Historical v3 artefacts are preserved; no model evaluation was rerun.
LABEL_PARSE_VERSION = "label-parse-v3.1-strict"

_VALID_CODE_STRS = frozenset("012")


def label_to_code(label):
    """Map a label name (str) to its official numeric code.

    Returns None for unknown names and for None, so a missing prediction
    never silently becomes code 1 (neutral)."""
    if label is None:
        return None
    return LABEL_TO_CODE.get(str(label).strip().lower())


def code_to_label(code):
    """Map an official numeric code to a label name (strict, v2).

    Accepts ONLY int 0/1/2 or the exact digit strings "0"/"1"/"2". Booleans
    are rejected explicitly (bool is an int subclass: True would cast to 1
    = neutral). Floats are rejected: int(1.5) == 1 must not decode to a
    label. Anything else returns None."""
    if isinstance(code, bool):
        return None
    if isinstance(code, int):
        return CODE_TO_LABEL.get(code)
    if isinstance(code, str):
        s = code.strip()
        if len(s) == 1 and s in _VALID_CODE_STRS:
            return CODE_TO_LABEL[int(s)]
    return None


def normalise_label(value):
    """Accept either a label name or a strict numeric code and return the
    canonical label name. None when neither form matches."""
    name = code_to_label(value)
    if name is not None:
        return name
    if isinstance(value, str) and value.strip().lower() in LABEL_TO_CODE:
        return value.strip().lower()
    return None
