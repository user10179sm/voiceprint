# voiceprint

**Conversational onboarding fork** of [sometimesyash/voiceprint](https://github.com/sometimesyash/voiceprint),
originally created by Yash and distributed under the MIT licence.

This version adds onboarding inside Codex: say **"learn how I write"**,
answer writing prompts, and optionally agree to specific sources such as your
own sent emails or original application answers. Codex infers the writing
context automatically. Progress is saved between conversations.

## Install this fork in Codex

Requires Python 3.10 or newer and the Codex CLI on your PATH. On macOS or Linux:

```bash
git clone https://github.com/user10179sm/voiceprint.git
cd voiceprint
python3 scripts/install_codex.py
```

You can also choose **Code > Download ZIP** on GitHub, extract it into a
permanent folder, open a terminal there and run the last command.

The installer links both skills into `~/.agents/skills` and registers this
checkout's Python server as `voiceprint`. It replaces an existing MCP server
with that name, and refuses to overwrite unrelated skill folders. It uses
only Python's standard library, with no package install or API key required
for the measurement server. Keep the checkout in place. Restart Codex, start
a new chat and say **"learn how I write"**. Your normal Codex account and
usage limits still apply.

Check the connection with `codex mcp get voiceprint`. To update a Git clone,
run `git pull` in this folder and restart Codex. To uninstall, run
`codex mcp remove voiceprint` and remove the two skill links from
`~/.agents/skills`. Your locally saved writing is retained until you delete it.

The recommended install is for macOS and Linux. Windows symlink permissions
and other hosts have not been tested with this installer. The plugin folders
are inherited distribution layouts, the commands above are the verified
installation route for this fork. See [verification notes](docs/onboarding-verification.md).

No personal emails, application answers or voice profiles are bundled.
The host needs its own source connections and the user's agreement before
reading existing writing. Copying the skill alone does not install the server.

Installation follows the official [local skill locations](https://learn.chatgpt.com/docs/build-skills)
and [MCP CLI configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli),
checked 20 October 2026.

## Original measurement tools

Measure how a person writes. Hold generated prose to the measurement.

Anything a model writes for you drifts toward the way models write: sentences
of similar length, hedge then assert, the occasional stacked fragment for
weight. Telling it to "write like me" does not fix that, because the
instruction is an adjective and the problem is a distribution.

This measures a person's writing and gives the model numbers to hit instead.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .

.venv/bin/vp build yash ~/Documents/writing
.venv/bin/vp brief yash --task "reply to a colleague about the timeline"
.venv/bin/vp check yash draft.md
```

## Read this before trusting a number

Identity is measured two ways, because they fail in different places. **Delta**
reads the function-word distribution and is the measure the literature
validates, but it needs a lot of text. **Texture** reads character n-grams,
which settle much sooner because a short passage contains thousands of them.

Held-out attribution against 24 authors, chance 4%:

| profile | 400w passage | 6,400w passage |
|---|---|---|
| Delta, 40,000 words | 28% | 92% |
| texture, 40,000 words | 65% | 90% |
| blended, 40,000 words | 65% | **95%** |

On real business email, three authors, holding out one text at a time: Delta
36%, texture 91%, blended 91%, against 33% chance. Short formulaic prose is
where Delta struggles most and texture earns its place.

The weighting follows the smaller of the draft and the profile, so a short
draft or a thin profile falls back to texture automatically. Full tables in
[docs/calibration.md](docs/calibration.md).

Two things follow.

**A small profile still cannot identify anyone.** Under about 1,500 words the
tool is near chance. It will build the profile, because the rhythm and
punctuation figures are real and useful for briefing a model, but it labels the
result `provisional`.

**Used comparatively it works at far smaller sizes** than it does used
absolutely. Asking which of two drafts is closer is a much easier question than
asking whether one passes.

## Reading a result

Distance shrinks as text grows, so a raw figure is not comparable across
lengths. A person's own 200-word passage scores about 2.3 where a stranger's
6,400-word passage scores about 1.0, which means a fixed band would fail the
author and pass the stranger.

So the number to read is **strangeness**: the share of writing by other people
that sits at least this close, at this draft's length. Under 5% is close, over
50% is off. It is computed from `data/scale.json`, measured across the same 24
authors.

```
strangeness 5%: that share of other people's writing sits this close at 132 words
```

## Not enough writing?

### Conversational onboarding

The `building-a-voiceprint` skill can now guide this inside Codex. The host
infers the context from the conversation, including job applications and
email, so the user does not choose a tone category. It suggests original
writing sources one at a time, records agreement or refusal, and fills gaps
with substantial writing prompts. Users can skip sources and begin writing.

The MCP tools are `voiceprint_onboard`, `voiceprint_source_decision`,
`voiceprint_add_sample` and `voiceprint_finish_onboarding`. They save progress
after each accepted passage, retain provenance, and keep validation writing
out of the profile-building corpus. The host supplies agreed source text,
these tools do not connect to mailboxes themselves. Assisted or unknown
authorship is rejected. Transcripts stay separate from written profiles.

Collections contain raw writing in `onboarding/<name>.json` under the profile
data directory. They can be inspected or deleted independently of the profile.
Revoking or narrowing source agreement removes its collection samples, a
saved profile changes only when rebuilt. A rebuild uses the saved collection,
it does not reconstruct an older standalone profile's original corpus. Brief
and check commands refuse a profile marked stale after source revocation.

`voiceprint_brief` and `voiceprint_check` accept a host-inferred `register`.
This lets Codex use conversational context when task keywords are ambiguous.
They report a pooled fallback when a context lacks enough writing.

Writing lengths and collection goals are guidance, not accuracy guarantees.
Validation rejects shared sequences of at least the sample minimum word count
across training and validation, but cannot detect paraphrases. A held-out
check alone does not establish an accuracy rate. The modified skill and MCP
server must be connected to the host, cloning this repo does not activate them.

### Prompts without a saved conversation

```bash
vp elicit yash
```

Returns prompts designed to draw natural prose, spread across registers so the
result is not an average of genres. They ask about things people have opinions
about, because argument produces rhythm where description produces lists, and
they never ask someone to describe how they write.

## What it measures

The features with the strongest replicated evidence for identifying an
individual author, all countable without a tagger or a model.

**Function word distributions.** How often someone reaches for *of* against
*from*, *but* against *however*. Unconscious, topic independent, and the basis
of authorship attribution since Mosteller and Wallace resolved the Federalist
Papers in 1964. Standardised against between-author variation measured from
`data/baseline.json`, which is what makes it Burrows's Delta rather than a
plain frequency distance.

**Character n-grams**, orders 3 to 5. Morphology and spelling habits that whole
words miss, and the arm that carries identity on anything short.

**Recurrent phrases.** The multi-word sequences someone returns to without
noticing. Forensic linguistics locates idiolect here more than in rare
vocabulary.

**Rhythm.** Sentence length, and more importantly its spread.

**Punctuation, per mark.** Simple, strong, easy to check.

**Register.** Person, contractions, abstraction, hedging, negation.

Content words are not used to identify anyone. They track subject matter and
community rather than the individual, so they are recorded as a topic
descriptor and kept out of the identity signal.

Correlated features are grouped, so a single habit like contracting moves the
distance once rather than three times, and marks absent from both texts are
excluded rather than diluting the average.

## How context works

A person writes an email differently from a report while remaining
recognisably themselves. So identity and convention are separated, and only the
second gives way to the occasion.

```
target = you + (1 - fidelity) * elasticity * (occasion - you)
```

Fidelity defaults to 0.8. Elasticity is declared per feature. Function words,
rhythm and punctuation habit sit at zero and never move. Length, formality and
hedging give way. Capitalisation and numeral style cannot be averaged at all,
so they go to whichever side owns them, usually the occasion.

## Where profiles live

One markdown file per person, under `VOICEPRINT_HOME` or the platform data
directory. Readable, editable, deletable.

```bash
vp show yash      # read it
vp remove yash    # delete it
```

The prose at the top is for the person it describes. A fenced JSON block at the
bottom is how the tool reads it back.

## Getting the writing

Ordered, and it stops rather than improvising.

1. Connected sources, if the host has any, and only after asking
2. Files you name
3. Text you paste
4. Nothing, in which case it says so and exits

There is no fifth step where it approximates. A connector is read only after an
explicit yes: if no consent prompt is wired up, every connector is treated as
declined, so a host that forgets cannot quietly read a mailbox.

## How much writing

| words | label | what it is worth |
|---|---|---|
| 10,000+ | stable | both measures hold, 57 to 95% in testing |
| 5,000 to 10,000 | usable | 45 to 62%, enough to brief with confidence |
| 1,500 to 5,000 | thin | texture carries identity, treat as directional |
| under 1,500 | provisional | shape is real, distances are not |

Register matters as much as volume. Genre moves writing at least as much as
identity does (Biber 1988), so tag samples with `--register` and the tool keeps
them apart, falling back to a pooled profile where one register is thin.

## Using it from an agent

An MCP server over stdio, so one implementation serves every client that speaks
the protocol.

```json
{
  "mcpServers": {
    "voiceprint": { "command": "python", "args": ["-m", "voiceprint.mcp"] }
  }
}
```

Ready-made manifests for Claude, Codex and Cursor are in the plugin
directories, generated from `skills/` by `scripts/sync.py`.

## As a library

Standard library only. The optional PDF reader is the sole extra.

```python
from voiceprint import store, blend_rules, against_rules

vp = store.load("yash")
profile = vp.profile_for("email")
rules = blend_rules(profile, None, fidelity=0.8)

report = against_rules(draft, rules, profile)
print(report.distance.overall, report.passed, report.reliable)
```

## What it will not do

It will not write for you. It measures, instructs and checks; the writing
happens elsewhere.

It will not identify an author from a paragraph. See the calibration table.

It will not defeat a provenance watermark. Those work on token sampling, not
syntax, and they exist so people can tell what a model wrote. This moves output
toward a person's measured statistics, which is a different thing.

It will not detect machine text reliably. The strongest signal for that is
token-level perplexity, which needs a language model, which this deliberately
does not have.

## Numbers that are still guesses

Named so they are not mistaken for method. The aggregate weighting
`0.45·identity + 0.35·scalar + 0.20·ngram`, the tolerance strictness curve in
`blend.py`, and the materiality floors in `check.py`. Each is a defensible
heuristic and none is calibrated.

Measured, not guessed: the confidence tiers, the reliable-length threshold, the
between-author dispersion behind Delta, the floor, ceiling and cap of the
two-arm weighting curve, and the length-to-distance table that turns a raw
figure into a percentile. All come from the scripts in `scripts/`.

## Reading

[docs/research.md](docs/research.md) for the evidence behind the feature set,
with verification status per source.
[docs/calibration.md](docs/calibration.md) for what the tool can resolve.
[docs/holdout-test.md](docs/holdout-test.md) for whether the brief changes the
writing, including the first version of that experiment which was too kind to
itself.
[docs/design-notes.md](docs/design-notes.md) for why it is built this way, and
the constraints that should survive a rewrite.

## Licence

MIT.
