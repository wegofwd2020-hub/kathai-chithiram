# KC-8 — Parent-facing privacy notice (informed consent)

**Labels:** P1, privacy, compliance
**Refs:** PRIVACY.md §8, §9 ("Draft parent-facing privacy notice"); CONTENT_SAFETY.md §6

## Why
`PRIVACY.md` is the *internal* data-handling commitment; §8 explicitly says a
plain-language, parent-facing version is a **separate deliverable**, and §9 lists
it as an open item. Consent capture already exists (`intake/`, KC's intake flow),
but consent is only *informed* if the parent is actually shown, in plain words,
what happens to their story before they agree. Today the intake flow asks for
consent with no notice presented and records nothing about which notice was in
effect.

## Acceptance criteria
- A plain-language, parent-readable privacy notice exists as a first-class doc
  (`docs/PARENT_PRIVACY_NOTICE.md`): what is collected, why, that stories are
  never used to train models, retention + right to delete, the human-review gate,
  and how to ask questions/delete. No legalese, no internal jargon.
- The notice is **versioned**, and the version is available in code so intake can
  reference the exact notice a parent saw.
- The parent-facing intake flow presents the notice (or a faithful summary + a
  pointer to the full text) **before** the consent questions.
- The intake record (`intake.json`) captures the `privacy_notice_version` that
  was in effect, so an informed-consent audit can tie a consent to a notice.
- The recorded version is non-sensitive (a version string, no story text/name)
  and is swept by the existing hard-delete like the rest of the record.

## Implementation notes
- Keep the notice text and its version together so they can't drift: a versioned
  constant + summary in the intake package, and the full doc under `docs/`.
- `submit_intake` records the current notice version in the intake record; the
  CLI shows the summary + doc pointer before asking for consent.
- Tests: the summary names the core commitments (no-training, deletion, human
  review); intake records the version; the intake flow shows the notice before
  consent. No real child data in fixtures.
- Out of scope: a web/hosted notice page and localization — this is the source
  notice + its wiring into the CLI intake. DPIA is KC-9.
