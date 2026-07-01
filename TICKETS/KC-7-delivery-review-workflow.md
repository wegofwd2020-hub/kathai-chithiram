# KC-7 — Review → approve → deliver workflow

**Labels:** P0, safety, privacy
**Status:** ✅ Done (2026-07-01) — `review/` module (`schema.py` `ReviewDecision`/`ReviewRecord`, `service.py` `load_review_bundle`/`review_story`), store `read_scene_script`/`read_intake_record`/`write_review_record`/`read_review_record`/`media_paths`, `ReviewError`, and a `kc review <id> --show|--approve|--reject` subcommand. 31 new tests; ruff + mypy clean.
**Refs:** CONTENT_SAFETY.md §6; PRIVACY.md §5, §8; `storage/store.py` (`mark_delivered`), `storage/retention.py`, `intake/service.py`, `cli.py`

## Why
The human-review gate is real but only *operational*: a rendered draft is stored
with `delivered=False`, the CLI prints a "⚠ DRAFT — a human must review" warning,
and the 30-day retention sweep purges anything still undelivered. The
`store.mark_delivered(story_id)` primitive exists but **nothing calls it** — there
is no coded path for a reviewer to inspect a draft, record an approval decision,
and promote it to delivered. Without this, approval is undocumented and an
approved-but-unmarked story is silently deleted inside the 30-day window.

## Acceptance criteria
- A reviewer-facing operation surfaces, for one story, the three things needed to
  judge it: the scene-script JSON, the rendered draft animation, and the intake
  record (consent flags + minimization warnings).
- An explicit **approve** action records a review decision (reviewer identity,
  decision, timestamp, and the scene-script/provider record it approved) and then
  calls `store.mark_delivered(story_id)`.
- An explicit **reject** action is also recorded (with reason) and leaves the story
  undelivered so the retention sweep can reclaim it.
- The safety pipeline (validate → render guards, KC-3/KC-4) must have passed before
  a story is eligible for approval; approval cannot bypass it.
- The approval record is durable and (like KC-1) removed on hard-delete; it must
  not contain raw story text.
- Delivery blocks retention deletion (existing behaviour) — verify a story approved
  inside the 30-day window is preserved and one left unreviewed is purged.

## Implementation notes
- Persist the decision as a new `review.json` in the story directory (parallel to
  `intake.json`); mirror its lifecycle in deletion (KC-1) and, if KC-5 lands,
  encryption.
- Add a `review`/`approve` CLI subcommand (and/or service method) that reads the
  artifacts and, on approval, writes `review.json` then calls `mark_delivered`.
  Keep it a thin orchestration over the existing storage primitives.
- OpenSpec docstrings; explicit `ReviewError` / `StoryNotFoundError`, no bare
  `except`; never log raw story text.
- Tests with mock stories: approve → `delivered=True` + `review.json` present +
  survives retention sweep; reject → stays undelivered + purged by sweep; approval
  refused when the safety pipeline has not passed.
- Note: this codifies today's human gate; per CONTENT_SAFETY.md §6 the gate itself
  stays until §5 automated enforcement is proven in production.
