"""Deterministic safety checks that run in code, independent of the LLM.

The LLM is good at judging candidates, but it should not be the only thing
standing between untrusted application text and a hiring action. Everything
here is plain Python so it can be unit-tested without an API key.
"""

import html
import re

# Phrases that look like someone addressing the model rather than a recruiter.
# A hit doesn't prove malice; it marks the application for human review and
# blocks automatic advancement.
INJECTION_PATTERNS = [
    r"ignore\s+(?:all\s+|your\s+|any\s+|the\s+)?(?:previous\s+|prior\s+|above\s+)?(?:instructions|rubric|rules|prompt)",
    r"disregard\s+(?:all\s+|your\s+|the\s+)?(?:previous\s+|prior\s+)?(?:instructions|rubric|rules)",
    r"system\s+(?:note|prompt|message|override)",
    r"you\s+are\s+now",
    r"score\s+(?:of\s+)?100",
    r"(?:advance|approve|hire)\s+this\s+candidate",
    r"</?\s*(?:system|instructions?|application)\b",
    r"\b(?:assistant|developer)\s*:",
]
_COMPILED = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]

# Score bands -> the only decision allowed for that score.
ADVANCE_MIN = 70
MORE_INFO_MIN = 40

DECISION_TOOLS = {"advance_to_interview", "reject", "request_more_info"}


def scan_for_injection(text: str) -> list[str]:
    """Return the matched snippets (empty list = nothing suspicious)."""
    return [m.group(0) for rx in _COMPILED for m in rx.finditer(text)]


def wrap_application(candidate_id: str, text: str) -> str:
    """Put untrusted text inside a data envelope it cannot close.

    Escaping < and > means the applicant can't write </application> and
    then continue "outside" the data block.
    """
    safe = html.escape(text, quote=False)
    return f'<application id="{html.escape(candidate_id)}">\n{safe}\n</application>'


def expected_action(score: int) -> str:
    if score >= ADVANCE_MIN:
        return "advance_to_interview"
    if score >= MORE_INFO_MIN:
        return "request_more_info"
    return "reject"


def check_decision(state: dict, tool_name: str, tool_input: dict) -> str | None:
    """Policy gate for decision tools. Returns an error message, or None if allowed.

    `state` is the per-candidate state kept by the executor:
    candidate_id, score, decision.
    """
    if tool_input.get("candidate_id") != state["candidate_id"]:
        return (f"candidate_id mismatch: you are reviewing '{state['candidate_id']}', "
                f"not '{tool_input.get('candidate_id')}'.")
    if state.get("decision"):
        return f"A decision ({state['decision']}) was already recorded for this candidate."
    if state.get("score") is None:
        return "Call score_application before choosing a next step."
    want = expected_action(state["score"])
    if tool_name != want:
        return (f"Policy: a score of {state['score']} maps to {want} "
                f"(advance >= {ADVANCE_MIN}, request_more_info {MORE_INFO_MIN}-{ADVANCE_MIN - 1}, "
                f"reject < {MORE_INFO_MIN}). Re-score with score_application if your score was wrong, "
                f"otherwise call {want}.")
    return None
