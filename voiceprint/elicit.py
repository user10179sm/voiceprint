"""Getting writing out of someone who has no archive.

The measurement problem has a supply-side answer as well as a statistical one.
Most people do have enough writing, it is simply scattered or unreachable, and
the rest can produce a few hundred words on demand if asked the right way.

These prompts are designed to pull unselfconscious prose. Two rules behind
them: never ask someone to describe how they write, because the description
will be aspirational and the writing will be stilted; and ask about something
they already have opinions about, because argument produces natural rhythm
where description produces lists.

Each prompt targets a register, so the answers can be tagged and kept apart
rather than pooled into an average of genres.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Prompt:
    register: str
    ask: str
    why: str
    words: int = 150


PROMPTS = (
    Prompt(
        "note",
        "Tell me about something you recently built, organised, learned or "
        "tried to fix. What got you started, what choices did you make, "
        "what went wrong and what did you think afterwards? Write the way "
        "you would explain it to someone you know. Use real details, "
        "without polishing your phrasing.",
        "A familiar story invites sustained writing without a formal template.",
        550),
    Prompt(
        "application",
        "Think of something you chose to work on without being told to. "
        "Explain what interested you, what you personally did, what was "
        "difficult and what happened. Use your own words and real details. "
        "This is a writing sample, not an answer to submit to an employer.",
        "A familiar experience supplies sustained personal explanation.",
        500),
    Prompt(
        "application",
        "Pick a kind of work you would like to do. Explain what draws you "
        "to it, which experiences shaped that interest and what you still "
        "want to learn. Write as yourself without trying to impress anyone.",
        "Motivation supplies a different kind of application prose.",
        400),
    Prompt(
        "email",
        "Think of the last email you wrote that you had to think about. "
        "Write it again from memory, to the same person, about the same "
        "thing. Do not look it up.",
        "Recall reproduces habit. Looking it up reproduces the original.",
        180),
    Prompt(
        "email",
        "Someone has asked you for a favour you are going to decline. Write "
        "the reply.",
        "Declining forces hedging, and how a person softens is individual.",
        120),
    Prompt(
        "note",
        "What is something in your work that most people get wrong, and what "
        "do you think is actually true?",
        "Disagreement produces argument, and argument produces rhythm.",
        250),
    Prompt(
        "note",
        "Describe the last thing you built or fixed, to a colleague who was "
        "not there. Not what it was, but what happened.",
        "Narrative pulls past tense and clause structure that description "
        "never reaches.",
        250),
    Prompt(
        "chat",
        "You are messaging a colleague to say a deadline is going to slip. "
        "Write the message.",
        "Short-form register, which differs sharply from long-form for most "
        "people.",
        60),
    Prompt(
        "memo",
        "Write the opening of a note recommending a decision to someone more "
        "senior than you. Just the first two paragraphs.",
        "Formal register under status pressure, where hedging and "
        "nominalisation peak.",
        200),
    Prompt(
        "essay",
        "What is a view you hold that people you respect disagree with, and "
        "why do you hold it anyway?",
        "Sustained argument, the longest natural prose most people produce "
        "unprompted.",
        350),
    Prompt(
        "note",
        "Explain something from your field to someone clever who knows "
        "nothing about it.",
        "Explanation produces analogy and sentence-length variation.",
        250),
)


def for_register(register: str) -> list[Prompt]:
    return [p for p in PROMPTS if p.register == register]


def plan(have_words: int, target: int = 2500) -> list[Prompt]:
    """Which prompts to ask, given how much writing already exists.

    Spread across registers first, because a profile built from one genre
    measures the genre. Depth within a register only after the spread is
    covered.
    """
    if have_words >= target:
        return []
    need = target - have_words
    chosen: list[Prompt] = []
    seen: set[str] = set()
    for p in sorted(PROMPTS, key=lambda x: -x.words):
        if p.register in seen:
            continue
        chosen.append(p)
        seen.add(p.register)
        need -= p.words
        if need <= 0:
            return chosen
    for p in PROMPTS:
        if p in chosen:
            continue
        chosen.append(p)
        need -= p.words
        if need <= 0:
            break
    return chosen


def brief(have_words: int, target: int = 2500) -> str:
    """What to put in front of someone who needs to supply writing."""
    chosen = plan(have_words, target)
    if not chosen:
        return (f"You already have {have_words:,} words, which is enough. "
                f"No need to write anything new.")

    total = sum(p.words for p in chosen)
    L = [f"There are {have_words:,} words to work with against a collection "
         f"goal of {target:,}. These prompts suggest about {total} words "
         f"of new writing. They may not close the whole gap. You can also "
         f"supply existing original writing. The goal is not an accuracy guarantee.",
         "",
         "Answer as many of these as you feel like, in your own words, "
         "without editing. Rough is better than polished: the polish is what "
         "gets measured away.",
         ""]
    for i, p in enumerate(chosen, 1):
        L.append(f"{i}. ({p.register}, ~{p.words} words) {p.ask}")
    L.append("")
    L.append("Do not try to write well. Write the way you would if nobody "
             "were going to read it.")
    return "\n".join(L)
