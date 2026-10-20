"""Reading the situation.

Before deciding how much of someone's voice to apply, the tool needs to know
what is being written. A note to a colleague and a board paper ask for
different things from the same person, and the honest answer is usually that
the person stays the same while the conventions move.

Context arrives one of three ways: a profile measured from real examples of
the target genre, a named register the caller already knows, or nothing at
all, in which case the writer's own voice stands unadjusted.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .corpus import Corpus, Sample
from .profile import Profile, _profile

REGISTERS = {
    "application": "Job applications and cover letters. Personal, specific and professional.",
    "spoken": "Transcribed speech. Kept separate from written samples.",
    "email": "Correspondence. Direct, addressed to someone.",
    "chat": "Short messages. Fragmentary, informal.",
    "memo": "Internal writing. Structured but plain.",
    "report": "Formal, evidenced, impersonal.",
    "deck": "Slide text. Compressed, designed to be spoken over.",
    "essay": "Extended argument in continuous prose.",
    "note": "Writing for oneself.",
    "docs": "Instructional. Second person, imperative.",
}

# Fidelity below this is refused: at some point the output stops being the
# person and starts being the genre wearing their name.
FLOOR = 0.5

CUES = [
    (r"\b(email|e-mail|inbox)\b", "email"),
    (r"\b(cover(ing)? letter|personal statement|supporting statement|"
     r"(job|internship|placement|graduate|spring week) applications?|"
     r"application for (a |an )?(job|internship|placement|graduate role)|"
     r"application (form|question|answer)|why (this|our) (role|company))\b",
     "application"),
    (r"\b(email|e-mail|reply|respond to|write back|inbox)\b", "email"),
    (r"\b(teams|slack|dm|message|chat|ping)\b", "chat"),
    (r"\b(memo|brief|one[- ]pager|internal)\b", "memo"),
    (r"\b(report|paper|submission|board|findings|analysis)\b", "report"),
    (r"\b(deck|slide|presentation|pitch)\b", "deck"),
    (r"\b(essay|article|post|blog|piece)\b", "essay"),
    (r"\b(note|jot|scratch)\b", "note"),
    (r"\b(readme|documentation|docs|guide|tutorial|instructions)\b", "docs"),
]

FORMAL = re.compile(
    r"\b(formal|official|board|executive|client|customer|external|legal|"
    r"regulator|publish)\b", re.I)
CASUAL = re.compile(
    r"\b(casual|informal|quick|friendly|team|colleague|internal|draft)\b", re.I)


@dataclass
class Context:
    """What the situation asks for, and how confident we are it asked."""
    register: str
    fidelity: float
    profile: Profile | None = None
    reason: str = ""

    def as_dict(self) -> dict:
        return {"register": self.register, "fidelity": self.fidelity,
                "reason": self.reason,
                "measured": self.profile is not None}


def infer(task: str, default_fidelity: float = 0.80) -> Context:
    """Guess the register from how the task was described.

    A guess, and labelled as one. Where it matters, measure the genre from real
    examples instead of inferring it from a sentence.
    """
    t = (task or "").lower()
    register = next((name for pattern, name in CUES if re.search(pattern, t)),
                    "unknown")

    fidelity = default_fidelity
    reason = f"register inferred as {register}"
    if FORMAL.search(t):
        fidelity = max(FLOOR, default_fidelity - 0.1)
        reason += ", formal cues, so convention is given more room"
    elif CASUAL.search(t):
        fidelity = min(0.95, default_fidelity + 0.1)
        reason += ", informal cues, so your own voice is held closer"

    if register == "unknown":
        fidelity = min(0.95, default_fidelity + 0.05)
        reason = ("no register cues found, so the writing stays as close to "
                  "your own as possible")
    return Context(register=register, fidelity=round(fidelity, 2), reason=reason)


def resolve(task: str, register: str | None = None,
            default_fidelity: float = 0.80) -> Context:
    """Use the host's conversational context, falling back to task cues."""
    ctx = infer(task, default_fidelity)
    if register is not None:
        if register not in REGISTERS and register != "unknown":
            raise ValueError(f"Unknown writing context {register!r}")
        ctx.register = register
        ctx.reason = f"register supplied by the host as {register}"
    return ctx


def from_examples(texts: list[str], register: str = "context") -> Profile | None:
    """Measure the target genre from real examples of it."""
    corpus = Corpus()
    corpus.extend(Sample(t, origin="context example", register=register)
                  for t in texts)
    return _profile(corpus.texts, register) if corpus.samples else None


def describe(register: str) -> str:
    return REGISTERS.get(register, "Unrecognised register.")
