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


def label_to_code(label):
    """Map a label name (str) to its official numeric code.

    Returns None for unknown names and for None, so a missing prediction
    never silently becomes code 1 (neutral)."""
    if label is None:
        return None
    return LABEL_TO_CODE.get(str(label).strip().lower())


def code_to_label(code):
    """Map an official numeric code (int or digit str) to a label name.

    Returns None if the code is not a valid official label."""
    try:
        return CODE_TO_LABEL.get(int(code))
    except (TypeError, ValueError):
        return None


def normalise_label(value):
    """Accept either a label name or a numeric code (int/str) and return
    the canonical label name. None when neither form matches."""
    name = code_to_label(value)
    if name is not None:
        return name
    if isinstance(value, str) and value.strip().lower() in LABEL_TO_CODE:
        return value.strip().lower()
    return None
