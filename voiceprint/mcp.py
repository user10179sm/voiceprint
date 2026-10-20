"""MCP server over stdio.

One implementation reaches every client that speaks MCP, which is how the
tool stays honest about being cross-platform: Claude, Codex, Cursor and the
rest get the same behaviour rather than four drifting copies.

    python -m voiceprint.mcp

Tools that read a profile check it exists and return a plain refusal if it
does not. None of them will invent one.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import context, onboarding, store
from .blend import DEFAULT_FIDELITY, blend
from .check import against_rules
from .corpus import Corpus, NoCorpus, Sample
from .distance import measure
from .profile import CONFIDENCE_NOTE, build
from .render import brief_markdown

PROTOCOL = "2024-11-05"

TOOLS = [
    {
        "name": "voiceprint_build",
        "description": (
            "Measure how someone writes and store the profile as markdown. "
            "Give it files, folders, or text the user has supplied. It will "
            "not invent a profile: if nothing readable is provided it says so."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "who this profile is for"},
                "paths": {"type": "array", "items": {"type": "string"},
                          "description": "files or folders of their own writing"},
                "text": {"type": "string", "description": "prose pasted directly"},
                "register": {"type": "string",
                             "description": "email, chat, memo, report, deck, essay, note, docs"},
                "overwrite": {"type": "boolean"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "voiceprint_brief",
        "description": (
            "Get writing instructions for a stored profile, tuned to the task. "
            "Call this BEFORE drafting anything in someone's voice. Returns "
            "measured targets, the phrases they reuse, and real examples."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "task": {"type": "string",
                         "description": "what is being written, in plain words"},
                "fidelity": {"type": "number",
                             "description": "0.5 to 1.0, default 0.8. Higher holds "
                                            "closer to their own voice."},
                "register": {"type": "string", "enum": list(context.REGISTERS) + ["unknown"],
                             "description": "Infer this from the conversation and task. "
                                            "Do not ask the user to choose a tone category."},
            },
            "required": ["name"],
        },
    },
    {
        "name": "voiceprint_check",
        "description": (
            "Hold a draft against a profile. Returns a voice distance and the "
            "measures that sit furthest out, with what to do about each. Call "
            "this after drafting and rewrite until it passes."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "draft": {"type": "string"},
                "task": {"type": "string"},
                "fidelity": {"type": "number"},
                "register": {"type": "string", "enum": list(context.REGISTERS) + ["unknown"]},
            },
            "required": ["name", "draft"],
        },
    },
    {
        "name": "voiceprint_elicit",
        "description": (
            "Get prompts that draw natural writing out of someone whose "
            "profile is too thin. Use when voiceprint_build reports a thin or "
            "provisional profile, or when there is no writing to point at. "
            "Returns questions to ask, spread across registers."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "target": {"type": "number",
                           "description": "words the profile should reach, "
                                          "default 2500"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "voiceprint_list",
        "description": "Which profiles exist on this machine.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "voiceprint_show",
        "description": "Read a stored profile back as prose.",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
]

TOOLS.extend([
    {
        "name": "voiceprint_onboard",
        "description": "Start or resume conversational onboarding. Returns progress and "
                       "one next source suggestion or writing prompt. Infer context from "
                       "the task, never ask the user to select a category. Does not read sources.",
        "inputSchema": {"type": "object", "properties": {
            "name": {"type": "string"},
            "task": {"type": "string", "description": "The user's current writing task"},
            "register": {"type": "string", "enum": list(context.REGISTERS) + ["unknown"],
                         "description": "Context inferred by the host from the conversation"},
        }, "required": ["name"]},
    },
    {
        "name": "voiceprint_source_decision",
        "description": "Record the user's agreement or refusal for one suggested source, "
                       "or record that it is unavailable. Only record accepted after an explicit "
                       "yes to the described scope. No source is read by this tool. Revoking "
                       "or changing scope removes its session samples, saved profiles need rebuilding.",
        "inputSchema": {"type": "object", "properties": {
            "name": {"type": "string"},
            "source": {"type": "string", "enum": list(onboarding.SOURCES)},
            "decision": {"type": "string", "enum": ["accepted", "declined", "unavailable"]},
            "scope": {"type": "string", "description": "The exact scope the user agreed to"},
        }, "required": ["name", "source", "decision"]},
    },
    {
        "name": "voiceprint_add_sample",
        "description": "Save one original writing passage verbatim and retain its provenance. "
                       "Confirm human authorship with the user or clear original-message evidence. "
                       "Never treat approval of an assistant draft as human authorship. "
                       "Validation passages stay out of the training corpus.",
        "inputSchema": {"type": "object", "properties": {
            "name": {"type": "string"}, "text": {"type": "string"},
            "source": {"type": "string", "enum": list(onboarding.SOURCES) + ["prompt", "pasted"]},
            "origin": {"type": "string", "description": "Specific original message, file or prompt"},
            "authorship": {"type": "string", "enum": ["human", "assisted", "unknown"]},
            "purpose": {"type": "string", "enum": ["training", "validation"]},
            "task": {"type": "string", "description": "What this sample was written for"},
            "register": {"type": "string", "enum": list(context.REGISTERS) + ["unknown"]},
            "prompt_id": {"type": "string", "description": "ID returned with an onboarding prompt"},
        }, "required": ["name", "text", "source", "origin", "authorship"]},
    },
    {
        "name": "voiceprint_finish_onboarding",
        "description": "Build the profile from saved original written training samples and "
                       "check separate validation writing. Does not establish an accuracy rate. "
                       "Requires validation writing. Existing profiles are protected by default.",
        "inputSchema": {"type": "object", "properties": {
            "name": {"type": "string"}, "overwrite": {"type": "boolean"},
        }, "required": ["name"]},
    },
])


def _text(body: str, error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": body}], "isError": error}


def _build(args: dict) -> dict:
    name = args["name"]
    corpus = Corpus()
    log = []

    for raw in args.get("paths") or []:
        try:
            from .ingest import read_path
            added = corpus.extend(read_path(raw, register=args.get("register", "unknown")))
            log.append(f"{raw}: {added} samples")
        except Exception as e:
            log.append(f"{raw}: {e}")

    if args.get("text"):
        s = Sample(args["text"], origin="supplied",
                   register=args.get("register", "unknown"))
        log.append(f"supplied text: {s.words} words"
                   if corpus.add(s) else "supplied text: too short")

    if not corpus.samples:
        return _text(
            "No writing was available, so no profile was built. Ask the user "
            "for files or paste some of their own prose. A voiceprint cannot "
            "be guessed from a name.\n\n" + "\n".join(log), error=True)

    vp = build(corpus, name)
    try:
        path = store.save(vp, overwrite=bool(args.get("overwrite")))
    except store.ProfileExists as e:
        return _text(str(e), error=True)

    return _text(
        f"Built {name} from {vp.words:,} words across {len(corpus)} samples. "
        f"Confidence {vp.pooled.confidence}. "
        f"{CONFIDENCE_NOTE[vp.pooled.confidence]}\n\nStored at {path}\n\n"
        + "\n".join(log))


def _brief(args: dict) -> dict:
    onboarding.require_current(args["name"])
    vp = store.load(args["name"])
    ctx = context.resolve(args.get("task", ""), args.get("register"),
                          float(args.get("fidelity", DEFAULT_FIDELITY)))
    profile = vp.profile_for(ctx.register)
    if profile is None:
        return _text(f"{args['name']} has no usable profile.", error=True)
    rules = blend(profile, None, ctx.fidelity)
    fallback = (f"Using the pooled profile because {ctx.register} has insufficient "
                "writing of its own.\n\n" if profile.register != ctx.register else "")
    return _text(f"{ctx.reason}.\n\n" + fallback + brief_markdown(rules, vp.name))


def _check(args: dict) -> dict:
    onboarding.require_current(args["name"])
    vp = store.load(args["name"])
    ctx = context.resolve(args.get("task", ""), args.get("register"),
                          float(args.get("fidelity", DEFAULT_FIDELITY)))
    profile = vp.profile_for(ctx.register)
    if profile is None:
        return _text(f"{args['name']} has no usable profile.", error=True)
    rules = blend(profile, None, ctx.fidelity)
    report = against_rules(args["draft"], rules, profile)
    fallback = (f"Using pooled writing for {ctx.register}, its own context is thin.\n\n"
                if profile.register != ctx.register else "")
    return _text(fallback + report.to_markdown())


def _onboard(args: dict) -> dict:
    return _text(json.dumps(onboarding.status(args["name"], args.get("task"),
                                             args.get("register")), indent=2))


def _source_decision(args: dict) -> dict:
    return _text(json.dumps(onboarding.decide_source(
        args["name"], args["source"], args["decision"], args.get("scope", "")), indent=2))


def _add_sample(args: dict) -> dict:
    return _text(json.dumps(onboarding.add_sample(
        args["name"], args["text"], args["source"], args["origin"], args["authorship"],
        args.get("purpose", "training"), args.get("task", ""), args.get("register"),
        args.get("prompt_id")), indent=2))


def _finish_onboarding(args: dict) -> dict:
    return _text(json.dumps(onboarding.finish(args["name"],
                                             bool(args.get("overwrite"))), indent=2))


def _elicit(args: dict) -> dict:
    from . import elicit
    have = store.load(args["name"]).words if store.exists(args["name"]) else 0
    return _text(elicit.brief(have, int(args.get("target", 2500))))


def _list(_: dict) -> dict:
    found = store.listing()
    if not found:
        return _text(f"No profiles yet. Build one with voiceprint_build. "
                     f"They live in {store.home()}.")
    return _text("\n".join(f"{n}  {p}" for n, p in found))


def _show(args: dict) -> dict:
    path = store.require(args["name"])
    body = path.read_text(encoding="utf8").split("```json voiceprint")[0]
    return _text(body.rstrip())


HANDLERS = {
    "voiceprint_onboard": _onboard,
    "voiceprint_source_decision": _source_decision,
    "voiceprint_add_sample": _add_sample,
    "voiceprint_finish_onboarding": _finish_onboarding,
    "voiceprint_build": _build,
    "voiceprint_brief": _brief,
    "voiceprint_check": _check,
    "voiceprint_elicit": _elicit,
    "voiceprint_list": _list,
    "voiceprint_show": _show,
}


def handle(request: dict) -> dict | None:
    """One request in, one response out, or None for a notification.

    A notification carries no id and must never be answered, whatever the
    method is.
    """
    if not isinstance(request, dict):
        return {"jsonrpc": "2.0", "id": None,
                "error": {"code": -32600, "message": "request must be an object"}}

    method = request.get("method")
    rid = request.get("id")
    is_notification = "id" not in request

    if method == "initialize":
        result = {"protocolVersion": PROTOCOL,
                  "capabilities": {"tools": {}},
                  "serverInfo": {"name": "voiceprint", "version": "0.1.0"}}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = request.get("params") or {}
        fn = HANDLERS.get(params.get("name"))
        if fn is None:
            result = _text(f"Unknown tool {params.get('name')!r}", error=True)
        else:
            try:
                result = fn(params.get("arguments") or {})
            except store.ProfileMissing as e:
                result = _text(str(e), error=True)
            except NoCorpus as e:
                result = _text(str(e), error=True)
            except Exception as e:
                result = _text(f"{type(e).__name__}: {e}", error=True)
    elif method == "ping":
        result = {}
    else:
        if is_notification:
            return None
        return {"jsonrpc": "2.0", "id": rid,
                "error": {"code": -32601, "message": f"unknown method {method}"}}

    return None if is_notification else {"jsonrpc": "2.0", "id": rid,
                                         "result": result}


def dispatch(payload) -> dict | list | None:
    """Handle one request or a batch, per JSON-RPC 2.0."""
    if isinstance(payload, list):
        if not payload:
            return {"jsonrpc": "2.0", "id": None,
                    "error": {"code": -32600, "message": "empty batch"}}
        out = [r for r in (handle(item) for item in payload) if r is not None]
        return out or None
    return handle(payload)


def serve(stdin=sys.stdin, stdout=sys.stdout) -> None:
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            response = {"jsonrpc": "2.0", "id": None,
                        "error": {"code": -32700, "message": "parse error"}}
        else:
            try:
                response = dispatch(payload)
            except Exception as e:
                response = {"jsonrpc": "2.0", "id": None,
                            "error": {"code": -32603,
                                      "message": f"{type(e).__name__}: {e}"}}
        if response is not None:
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()


if __name__ == "__main__":
    serve()
