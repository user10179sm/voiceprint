---
name: building-a-voiceprint
description: Build or improve a writing voice profile through conversational onboarding, original writing sources and substantial writing prompts. Use for "learn how I write", "capture my style", "build my voiceprint", or a missing or thin profile. Collects real prose, never generates a substitute.
---

# Building a voiceprint

Collect writing the person actually produced. Background facts, approved
assistant drafts and summaries about the person do not establish their voice.
The tool measures samples into a profile, it does not train an LLM.

## Start or resume the conversation

Call `voiceprint_onboard` with the person's name and their current writing
task. Infer `register` from the conversation, document or form when useful.
The user should not have to choose a tone or category. An employer's
application question is `application`, correspondence is `email`, and a
message to a friend is `chat`. Use purpose and audience rather than isolated
keywords. An email about an application is still an email.

When the purpose is unknown, begin with general writing. Ask about the task
only if ambiguity would materially change what you need. Do not guess
personal facts to fill gaps.

Each response contains saved progress and one `next_step`. Ask one question
at a time and wait for the answer. Resume from the saved collection in later
turns, rather than restarting or asking an already answered question.

## Offer sources dynamically

Offer a relevant source the host can actually access or the user can supply.
Describe exactly what you propose reading and ask for agreement before using
a connector. Record the result with `voiceprint_source_decision`, including
the agreed scope for `accepted`. Mark inaccessible sources `unavailable`.
The tools themselves do not connect to mailboxes or scan account history.

Useful sources include:

- The person's paragraphs in sent emails, excluding replies and signatures.
- Original application answers from before any assistant rewriting.
- Their own messages to an assistant, especially explanations and corrections.
- Personal notes, project explanations and society or team updates.
- Voice-note transcripts, labelled `spoken` and kept out of written profiles.

Adapt the order to the task, host capabilities and the user's replies. A
decline means move on. Do not access the same material through another route.
An acceptance applies only to its described scope. Ask again before expanding
it. If they reverse a decision or narrow its scope, update the record. This
removes that source's collected samples, but an existing profile must be
rebuilt before the change reaches it. Brief and check tools refuse to use
the stale profile. The old file remains inspectable and can also be deleted.

If the user asks to skip existing sources and write something new, record
the remaining suggestions as declined because of that choice. Move directly
to a writing prompt. Do not make them decline each source separately.

## Save original passages

Read only the agreed material. Separate their words from other people's
messages, form questions, templates, quoted history and generated answers.
Use clear original-message evidence or the user's confirmation for authorship.
If attribution is uncertain, ask one focused question or exclude the sample.
Approving an assistant's wording does not make it original human writing.

Call `voiceprint_add_sample` for each passage, retaining its text verbatim,
specific `origin`, `source` and `authorship`. Infer the passage's `register`
from its own context. Do not tag an old email as an application answer just
because the current task is a job application. Use `purpose: training` for
the writing that will build the profile.

The tool rejects assisted or unknown authorship, samples below its word
minimum, duplicate passages and shared sequences between training and
validation. It cannot independently prove authorship or detect paraphrases.
Save each accepted passage immediately so an interruption loses no progress.

## Fill gaps with substantial writing

Call `voiceprint_onboard` again. When its next step is `prompt`, present that
one question conversationally. Keep the internal `prompt_id` for saving the
answer, do not show category menus or implementation details to the user.

Invite a substantial account of something familiar. For longer explanations,
roughly 400 to 600 words is a suggested starting point, not a requirement or
an accuracy threshold. Emails and chats can be naturally shorter. Do not pad
short answers or make the person imitate a formal voice.

Let them write without supplying a model answer, starter paragraph or rewrite.
Ask about real experiences, opinions or choices, rather than asking them to
describe their style. Preserve the answer verbatim and save it with
`source: prompt` and the returned `prompt_id`. Report its actual word count
against the suggestion. They may stop early, continue or supply more sources.

If all built-in prompts are exhausted before there is enough material,
explain the gap and offer one fresh question on a different familiar topic.
Save custom answers without a built-in prompt ID, with a descriptive origin
and a context inferred by the host. Do not repeat already used prompts to
inflate the word count.

## Check with separate writing

Reserve a separate original passage with `purpose: validation`. Ideally it
matches the current writing task and discusses different material. Never use
it in training, prompt selection examples or profile exemplars. The user may
supply this before reaching the collection goal if they want to stop early.

Call `voiceprint_finish_onboarding`. It builds only from original written
training samples and checks the validation passages separately. Existing
profiles require explicit replacement via `overwrite: true`. When rebuilding,
explain that this uses the session's saved samples. It cannot recover the
full corpus from an older standalone profile.

Show where the collection and profile were saved, what contexts are covered,
the actual confidence label and any pooled fallback or short-sample limits.
Do not equate a passed check, reaching a word goal or one held-out passage
with proven accuracy. Do not call a provisional profile reliable.

The collection contains raw text under `VOICEPRINT_HOME/onboarding/` or the
platform data directory. The profile contains measurements and excerpts.
Explain these local files can be inspected or deleted independently. Do not
claim the whole conversation stays on-device, the host handles the chat and
any connector access.

## When MCP tools are unavailable

The same operations are available in `voiceprint.onboarding` as `status`,
`decide_source`, `add_sample` and `finish`. `add_sample` calls its prompt-ID
parameter `prompt`. Use the host's Python tools if available. Do not claim
the integration is active merely because the repo was cloned.

For a one-off file build, the existing CLI remains available:

```bash
vp build yash ~/Documents/writing --register email
vp elicit yash
vp show yash
```
