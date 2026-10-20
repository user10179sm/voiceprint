# Conversational onboarding verification

Implementation checked 18 October 2026. Publication checks repeated 20 October 2026.

## Fork installation checks, 20 October 2026

- All 159 tests passed again.
- `scripts/sync.py --check` reported up to date and all eight skill copies passed frontmatter checks.
- The new `scripts/install_codex.py` was run against a temporary Codex configuration and skill directory.
- A fresh installation, repeated installation and refusal of an unrelated existing skill directory passed.
- The installed command launched from outside the checkout, advertised all four onboarding tools and inferred application context in a synthetic onboarding call.
- No package download or API key was needed for this installation check.
- The changed source, tests, skills and documentation were checked for local personal paths and writing samples before publication.
- The original MIT licence and upstream attribution are retained.

The verified install route uses local skills and a stdio server on macOS.
Windows, a newly installed user's live Codex chat and plugin marketplace
installation have not been tested. Existing plugin manifests are inherited
from upstream and are not the recommended installation route for this fork.

## Verified so far

- The final full suite passed with 159 tests, including 25 new onboarding and context tests.
- The skill validator accepted both revised skills.
- Plugin skill copies were regenerated using `scripts/sync.py`.
- Source decisions and sample collection were exercised through MCP handlers.
- A fresh Python process resumed the saved collection.
- Validation writing was excluded from the built profile's word count and manifest.

## Additional checks passed

- A context without samples still receives prompts when another context has sufficient material.
- Revoked source samples block brief and check until the profile is rebuilt.
- A running stdio MCP server advertised all four tools and handled a synthetic conversation.
- The server was restarted during collection and resumed its progress.
- That flow exercised source refusal, new writing, authorship rejection, duplicate rejection,
  held-out checking, automatic email fallback and overwrite protection.
- No browser artifact was added. The feature is conversational and local to the backend.
- No real mailbox content or personal writing was used for these checks.

## Not verified

- Automatic skill invocation or tool registration in a live Codex chat.
- A real user's onboarding responses or a measured improvement in writing quality.
- Real mailbox or document access. The host must provide agreed passages.
- Independent proof of sample authorship or detection of paraphrased overlap.

## Local Codex installation

Verified 18 October 2026.

- Both skills are linked into the user's Codex skills directory and match the edited sources.
- The global `voiceprint` MCP server is registered and enabled.
- Its configured launch command starts outside the repository and advertises the four new tools.
- An isolated onboarding call through that command inferred application context successfully.
- No real writing sources were read and no personal profile was created.
- Invocation from the desktop chat itself still needs verification on a subsequent turn.
