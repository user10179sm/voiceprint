"""Resumable collection of original writing, separate from its measurements."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
import os
from pathlib import Path
import tempfile

from . import context, store, text as T
from .blend import blend
from .check import against_rules
from .corpus import Corpus, MIN_SAMPLE_WORDS, NoCorpus, Sample
from .elicit import PROMPTS, Prompt
from .profile import CONFIDENCE_NOTE, USABLE_WORDS, build, confidence

SOURCES = {
    "sent_email": "Your paragraphs in sent emails, without quoted replies or signatures",
    "applications": "Original application answers from before any assistant rewriting",
    "own_messages": "Your own messages explaining ideas or correcting an assistant",
    "notes": "Personal notes and explanations of projects you worked on",
    "society_messages": "Messages and updates you wrote for a society or team",
    "transcripts": "Transcribed voice notes, kept in a separate spoken context",
}


def path_for(name: str) -> Path:
    return store.home() / "onboarding" / f"{store.slug(name)}.json"


def _load(name: str) -> dict:
    path = path_for(name)
    if path.exists():
        return json.loads(path.read_text(encoding="utf8"))
    return {"schema": 1, "name": name, "task": "", "register": "unknown",
            "target": USABLE_WORDS, "sources": {}, "samples": [],
            "profile_stale": False}


def _save(session: dict) -> None:
    path = path_for(session["name"])
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".session-")
    try:
        with os.fdopen(fd, "w", encoding="utf8") as stream:
            json.dump(session, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def prompt_id(prompt: Prompt) -> str:
    return hashlib.sha256(prompt.ask.encode("utf8")).hexdigest()[:12]


def choose_prompt(candidates: Sequence[Prompt], register: str,
                  words_by_register: Mapping[str, int]) -> Prompt | None:
    """Choose one unanswered prompt using the task and existing coverage."""
    if not candidates:
        return None
    focused = [p for p in candidates if p.register == register]
    if focused and words_by_register.get(register, 0) < USABLE_WORDS:
        return max(focused, key=lambda p: p.words)
    return min(candidates, key=lambda p: (
        words_by_register.get(p.register, 0), -p.words))


def _summary(session: dict) -> dict:
    counts: dict[str, int] = {}
    for sample in session["samples"]:
        if sample["purpose"] == "training" and sample["register"] != "spoken":
            register = sample["register"]
            counts[register] = counts.get(register, 0) + sample["words"]
    total = sum(counts.values())
    return {"name": session["name"], "task": session["task"],
            "register": session["register"], "training_words": total,
            "words_by_register": counts, "confidence": confidence(total),
            "collection_goal": session["target"],
            "validation_samples": sum(s["purpose"] == "validation"
                                      and s["register"] != "spoken"
                                      for s in session["samples"]),
            "spoken_words": sum(s["words"] for s in session["samples"]
                                if s["register"] == "spoken"),
            "session_path": str(path_for(session["name"])),
            "profile_stale": session.get("profile_stale", False),
            "samples": [{k: v for k, v in s.items() if k != "text"}
                        for s in session["samples"]],
            "sources": session["sources"],
            "note": "Collection goals are not accuracy guarantees. "
                    "Saved profiles change only when onboarding is built."}


def _next_step(session: dict, summary: dict) -> dict:
    priority = {"email": "sent_email", "application": "applications",
                "note": "notes", "chat": "own_messages"}.get(session["register"])
    sources = sorted(SOURCES, key=lambda source: source != priority)
    context_words = summary["words_by_register"].get(session["register"], 0)
    need_more = (summary["training_words"] < session["target"] or
                 (session["register"] not in ("unknown", "spoken")
                  and context_words < USABLE_WORDS))
    for source in sources:
        if need_more and source not in session["sources"]:
            return {"kind": "source", "source": source,
                    "suggestion": SOURCES[source],
                    "instruction": "Offer this source if available. Describe the exact "
                                   "scope and ask one question. Do not read it before "
                                   "agreement. Record unavailable sources and move on."}
    answered = {s.get("prompt_id") for s in session["samples"]}
    candidates = [p for p in PROMPTS if prompt_id(p) not in answered]
    prompt = choose_prompt(candidates, session["register"], summary["words_by_register"])
    if need_more and prompt:
        return {"kind": "prompt", "prompt_id": prompt_id(prompt),
                "register": prompt.register, "question": prompt.ask,
                "suggested_words": prompt.words,
                "instruction": "Ask only this question. Length is a suggestion, "
                               "not a minimum. Preserve the answer verbatim."}
    if not summary["validation_samples"]:
        return {"kind": "validation", "register": session["register"],
                "question": "Please share a separate piece you wrote in this context, "
                            "or write about a different familiar experience. We will "
                            "keep it out of the profile and use it to check the result.",
                "suggested_words": 500}
    return {"kind": "build", "instruction": "Build from training samples only. "
            "If the goal is unmet, explain that the profile remains limited. "
            "Offer more original sources or a fresh prompt if they want to continue."}


def status(name: str, task: str | None = None,
           register: str | None = None) -> dict:
    session = _load(name)
    if task is not None or register is not None:
        session["task"] = task if task is not None else session["task"]
        session["register"] = context.resolve(session["task"], register).register
    _save(session)
    result = _summary(session)
    result["next_step"] = _next_step(session, result)
    return result


def decide_source(name: str, source: str, decision: str, scope: str = "") -> dict:
    if source not in SOURCES:
        raise ValueError(f"Unknown source {source!r}")
    if decision not in ("accepted", "declined", "unavailable"):
        raise ValueError("Decision must be accepted, declined or unavailable")
    if decision == "accepted" and not scope.strip():
        raise ValueError("Describe the specific source scope the user agreed to")
    session = _load(name)
    previous = session["sources"].get(source)
    session["sources"][source] = {"decision": decision, "scope": scope}
    removed = 0
    if decision != "accepted" or (previous and previous["scope"] != scope):
        kept = [s for s in session["samples"] if s["source"] != source]
        removed = len(session["samples"]) - len(kept)
        session["samples"] = kept
        if removed and store.exists(name):
            session["profile_stale"] = True
    _save(session)
    result = status(name)
    result["removed_samples"] = removed
    return result


def require_current(name: str) -> None:
    """Prevent writing with a profile whose source agreement was revoked."""
    if path_for(name).exists() and _load(name).get("profile_stale"):
        raise ValueError("Source agreement changed after this profile was saved. "
                         "Rebuild from the remaining agreed samples before writing "
                         "with it, or remove the saved profile.")


def _shingles(words: list[str]) -> set[tuple[str, ...]]:
    return {tuple(words[i:i + MIN_SAMPLE_WORDS])
            for i in range(len(words) - MIN_SAMPLE_WORDS + 1)}


def add_sample(name: str, text: str, source: str, origin: str,
               authorship: str, purpose: str = "training",
               task: str = "", register: str | None = None,
               prompt: str | None = None) -> dict:
    if authorship != "human":
        raise ValueError("Use only confirmed original human writing. "
                         "Assisted or unknown authorship is not voice evidence.")
    if purpose not in ("training", "validation"):
        raise ValueError("Purpose must be training or validation")
    if not origin.strip():
        raise ValueError("Describe where this passage came from")
    session = _load(name)
    if source not in ("prompt", "pasted"):
        if session["sources"].get(source, {}).get("decision") != "accepted":
            raise ValueError("The user has not agreed to this source")
    if source == "transcripts":
        register = "spoken"
    elif prompt is not None:
        matched = next((p for p in PROMPTS if prompt_id(p) == prompt), None)
        if matched is None:
            raise ValueError("Unknown prompt id")
        register = matched.register
    else:
        source_task = {"sent_email": "email", "applications": "job application",
                       "own_messages": "chat", "notes": "note",
                       "society_messages": "chat"}.get(source, "")
        register = context.resolve(task or source_task or session["task"], register).register
    sample = Sample(text, origin=origin, register=register)
    if not sample.usable:
        raise ValueError(f"This passage has {sample.words} words, below the "
                         f"{MIN_SAMPLE_WORDS}-word sample minimum")
    words = T.words(sample.text)
    for previous in session["samples"]:
        old = T.words(previous["text"])
        normal, old_normal = " ".join(words), " ".join(old)
        if f" {normal} " in f" {old_normal} " or f" {old_normal} " in f" {normal} ":
            raise ValueError("This writing is already in the collection")
        if purpose != previous["purpose"] and _shingles(words) & _shingles(old):
            raise ValueError("Training and validation share a passage. "
                             "Use separate writing for an independent check.")
    session["samples"].append({"text": sample.text, "source": source,
        "origin": origin, "register": register, "authorship": authorship,
        "purpose": purpose, "words": sample.words, "prompt_id": prompt})
    _save(session)
    result = status(name)
    result["added_words"] = sample.words
    return result


def finish(name: str, overwrite: bool = False) -> dict:
    session = _load(name)
    corpus = Corpus()
    for s in session["samples"]:
        if s["purpose"] == "training" and s["register"] != "spoken":
            corpus.add(Sample(s["text"], origin=s["origin"], register=s["register"]))
    if not corpus.samples:
        raise NoCorpus("No original written training samples are available")
    validation = [s for s in session["samples"]
                  if s["purpose"] == "validation" and s["register"] != "spoken"]
    if not validation:
        raise NoCorpus("Supply a separate original written validation sample first")
    vp = build(corpus, name)
    checks = []
    for s in validation:
        profile = vp.profile_for(s["register"])
        report = against_rules(s["text"], blend(profile), profile)
        checks.append({"origin": s["origin"], "requested_register": s["register"],
                       "profile_register": profile.register,
                       "profile_confidence": profile.confidence,
                       "report": report.as_dict()})
    path = store.save(vp, overwrite=overwrite)
    session["profile_stale"] = False
    _save(session)
    return {"profile_path": str(path), "training_words": vp.words,
            "confidence": vp.pooled.confidence,
            "confidence_note": CONFIDENCE_NOTE[vp.pooled.confidence],
            "validation": checks,
            "limitations": ["A held-out similarity check does not establish an accuracy rate.",
                "Short validation passages and thin profiles limit interpretation.",
                "Overlap checks catch shared word sequences, not paraphrases.",
                "Spoken samples stay in the collection and are excluded from written profiles."]}
