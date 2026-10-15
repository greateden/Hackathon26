"""Opt-in Task A prompt; assign to SubmissionJudge.system_prompt explicitly.

Not imported by production entrypoints. No model-quality claim is implied.
"""
from nli_judge import SYSTEM_PROMPT


VOTE_IDENTITY_INSTRUCTIONS = (
    "Decision order: (1) Identify the specified proposal from explicit evidence in "
    "the supplied passages and select its vote_reference. Its presence elsewhere "
    "in the booklet, request metadata, or topic similarity alone does not establish "
    "identity. If identity is unresolved, keep ambiguous or unrecognised; do not "
    "invent an identity or reference. (2) Determine whether the claim concerns that "
    "proposal, without changing an evidence-grounded identity because the claim is "
    "unrelated. (3) Use entailment when the evidence supports the claim, contradiction "
    "only when the evidence establishes that the claim is false, and neutral when "
    "the evidence neither establishes nor refutes it. An unrelated claim is not "
    "automatically a contradiction: without support or refutation, use neutral. "
    "A recognised proposal can have a neutral claim; retain its grounded "
    "vote_reference while using insufficient evidence_status and empty evidence_refs. "
    "Do not invent evidence, citations, or missing information."
)

# Insert before the legacy schema marker: build_messages replaces that schema
# with the existing six-field Task A contract, leaving this instruction intact.
VOTE_IDENTITY_V1 = SYSTEM_PROMPT.replace(
    "\nReply with EXACTLY", "\n\n" + VOTE_IDENTITY_INSTRUCTIONS + "\nReply with EXACTLY", 1
)
