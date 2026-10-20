"""The command line.

    vp build NAME [sources...]   measure someone's writing
    vp show NAME                 read the profile back
    vp brief NAME [--task ...]   the instruction for a writing agent
    vp check NAME FILE           how far a draft sits from the profile
    vp diff NAME FILE            the same, feature by feature
    vp list                      what profiles exist
    vp remove NAME

Every command that reads a profile checks it exists first and says so if not.
Nothing is inferred from a name alone.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from voiceprint import context, elicit, onboarding, store
from voiceprint.blend import DEFAULT_FIDELITY, blend
from voiceprint.check import against_rules
from voiceprint.corpus import Ladder, NoCorpus
from voiceprint.profile import CONFIDENCE_NOTE, build
from voiceprint.render import brief_markdown
from voiceprint.sources import discover


def _consent(stream=sys.stdin) -> callable:
    def ask(description: str) -> bool:
        if not stream.isatty():
            return False
        print(f"\n{description}")
        return input("Read it? [y/N] ").strip().lower() in ("y", "yes")
    return ask


def _read_stdin() -> str | None:
    if sys.stdin.isatty():
        return None
    data = sys.stdin.read()
    return data if data.strip() else None


def cmd_build(args) -> int:
    ladder = Ladder(connectors=[] if args.no_sources else discover(),
                    ask=_consent())
    pasted = args.text or _read_stdin()
    try:
        corpus, log = ladder.gather(files=args.sources or None, pasted=pasted,
                                    register=args.register)
    except NoCorpus as e:
        print(f"\n{e}", file=sys.stderr)
        return 2

    for line in log:
        print(f"  {line}")

    vp = build(corpus, args.name)
    try:
        path = store.save(vp, overwrite=args.force)
    except store.ProfileExists as e:
        print(f"\n{e}", file=sys.stderr)
        return 3

    p = vp.pooled
    print(f"\n{vp.words:,} words, {len(corpus)} samples, "
          f"{p.windows} windows, confidence {p.confidence}.")
    print(CONFIDENCE_NOTE[p.confidence])
    for note in vp.notes[1:]:
        print(f"  {note}")
    print(f"\nwrote {path}")
    return 0


def cmd_show(args) -> int:
    path = store.require(args.name)
    if args.json:
        print(json.dumps(store.load(args.name).as_dict(), indent=2))
        return 0
    text = path.read_text(encoding="utf8")
    print(text.split("```json voiceprint")[0].rstrip())
    return 0


def cmd_brief(args) -> int:
    onboarding.require_current(args.name)
    vp = store.load(args.name)
    ctx = context.infer(args.task or "", args.fidelity)
    profile = vp.profile_for(args.register or ctx.register)
    if profile is None:
        print(f"{args.name} has no usable profile.", file=sys.stderr)
        return 4

    target = None
    if args.like:
        texts = [Path(p).read_text(encoding="utf8", errors="ignore")
                 for p in args.like]
        target = context.from_examples(texts, ctx.register)

    rules = blend(profile, target, ctx.fidelity)
    out = brief_markdown(rules, vp.name)
    if args.out:
        Path(args.out).write_text(out, encoding="utf8")
        print(f"wrote {args.out}")
    else:
        print(out)
    return 0


def cmd_check(args) -> int:
    onboarding.require_current(args.name)
    vp = store.load(args.name)
    draft = (Path(args.draft).read_text(encoding="utf8")
             if args.draft != "-" else sys.stdin.read())
    ctx = context.infer(args.task or "", args.fidelity)
    profile = vp.profile_for(args.register or ctx.register)
    if profile is None:
        print(f"{args.name} has no usable profile.", file=sys.stderr)
        return 4

    rules = blend(profile, None, ctx.fidelity)
    report = against_rules(draft, rules, profile)
    print(json.dumps(report.as_dict(), indent=2) if args.json
          else report.to_markdown())
    return 0 if report.passed else 1


def cmd_diff(args) -> int:
    from voiceprint.distance import measure
    vp = store.load(args.name)
    profile = vp.profile_for(args.register)
    draft = (Path(args.draft).read_text(encoding="utf8")
             if args.draft != "-" else sys.stdin.read())
    d = measure(draft, profile, worst=args.top)
    s = d.strangeness
    print(f"identity {d.identity:.3f} from {d.arm}  "
          f"(delta {d.delta:.3f} weight {d.delta_weight:.2f}, "
          f"texture {d.texture:.3f})")
    if s is not None:
        print(f"strangeness {s:.0%}: that share of other people's writing "
              f"sits this close at {d.words} words")
    print(f"scalars {d.scalar:.3f}  n-grams {d.ngram:.3f}  "
          f"overall {d.overall:.3f}  ({d.verdict()})")
    print(f"support {d.support_words} words\n")
    print(f"{'measure':38s} {'draft':>10s} {'yours':>10s} {'sd':>8s} {'z':>7s}")
    for dev in d.worst:
        print(f"{dev.feature:38s} {dev.observed:10g} {dev.expected:10g} "
              f"{dev.sd:8g} {dev.z:7.2f}")
    return 0


def cmd_elicit(args) -> int:
    have = 0
    if store.exists(args.name):
        have = store.load(args.name).words
    print(elicit.brief(have, args.target))
    return 0


def cmd_list(args) -> int:
    found = store.listing()
    if not found:
        print(f"No profiles in {store.home()}. Build one with `vp build`.")
        return 0
    for name, path in found:
        print(f"{name:24s} {path}")
    return 0


def cmd_remove(args) -> int:
    if store.delete(args.name):
        print(f"removed {args.name}")
        return 0
    print(f"no profile named {args.name}", file=sys.stderr)
    return 1


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="vp", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    b = sub.add_parser("build", help="measure someone's writing")
    b.add_argument("name")
    b.add_argument("sources", nargs="*", help="files or folders")
    b.add_argument("--text", help="prose passed directly")
    b.add_argument("--register", default="unknown")
    b.add_argument("--no-sources", action="store_true",
                   help="skip connected sources entirely")
    b.add_argument("-f", "--force", action="store_true", help="overwrite")
    b.set_defaults(fn=cmd_build)

    s = sub.add_parser("show", help="read a profile")
    s.add_argument("name")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_show)

    r = sub.add_parser("brief", help="instruction for a writing agent")
    r.add_argument("name")
    r.add_argument("--task", help="what is being written")
    r.add_argument("--register")
    r.add_argument("--like", nargs="*", help="examples of the target genre")
    r.add_argument("--fidelity", type=float, default=DEFAULT_FIDELITY)
    r.add_argument("-o", "--out")
    r.set_defaults(fn=cmd_brief)

    c = sub.add_parser("check", help="hold a draft to the profile")
    c.add_argument("name")
    c.add_argument("draft", help="file, or - for stdin")
    c.add_argument("--task")
    c.add_argument("--register")
    c.add_argument("--fidelity", type=float, default=DEFAULT_FIDELITY)
    c.add_argument("--json", action="store_true")
    c.set_defaults(fn=cmd_check)

    d = sub.add_parser("diff", help="feature by feature")
    d.add_argument("name")
    d.add_argument("draft")
    d.add_argument("--register")
    d.add_argument("--top", type=int, default=15)
    d.set_defaults(fn=cmd_diff)

    sub.add_parser("list", help="profiles on this machine").set_defaults(fn=cmd_list)

    e = sub.add_parser("elicit", help="prompts to get more writing")
    e.add_argument("name")
    e.add_argument("--target", type=int, default=2500,
                   help="words the profile should reach")
    e.set_defaults(fn=cmd_elicit)

    x = sub.add_parser("remove", help="delete a profile")
    x.add_argument("name")
    x.set_defaults(fn=cmd_remove)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return args.fn(args)
    except store.ProfileMissing as e:
        print(str(e), file=sys.stderr)
        return 2
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
