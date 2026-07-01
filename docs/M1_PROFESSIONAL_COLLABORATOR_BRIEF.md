# M1 progress engine — brief for the professional collaborator

**Status:** Draft v0.1 (2026-07-01) · **For:** a trained therapist / professional
collaborator (ADR-002 Decision 7.1) · **Owner:** WeGoFwd2020

> ADR-002 deliberately leaves the *clinical judgment* out of engineering's hands.
> The progress engine may not be built until a trained professional defines what
> counts as a meaningful signal. This brief states exactly what we need from you,
> and — just as important — what we will **not** do with it.

## What Kathai Chithiram is (one paragraph)

A parent writes a short story about their child (often a child with special
needs); we turn it into a calm, captioned animation the child watches. After a
viewing, the parent records a tiny, fixed **feedback** primitive — nothing
free-text. Over repeated sessions, that data accrues against a **goal**. We would
like a child's real response to *inform* — never dictate — what story comes next.

## The data you'd be reasoning over

Each session yields one record, and only these fields (no notes, no diagnosis, no
identifiers beyond opaque ids):

- `prompt_level` ∈ { refused, prompted, independent } — how much help the child
  needed with the target behaviour.
- `completed` — whether the child completed the target behaviour (yes/no).
- `mood_checkin` — a short, calm 1–5 ordinal (1 = most upset, 5 = happiest).
- `recorded_at`, plus the opaque `goal_id` and `story_id`.

We already surface these raw, per session, over a window — see the "evidence
view" (`progress/evidence.py`): it lists the sessions and their exact values and
computes **nothing** derived. That transparency is a hard requirement (Decision
7.2).

## What we need you to define (Decision 7.1)

Engineering will **not** pick these — they are clinical judgment:

1. **Window K** — how many recent sessions a signal should consider, and whether
   it is a fixed count, a time window, or both.
2. **Thresholds** — what values, over K, constitute a meaningful signal (e.g.
   what pattern of `independent` would suggest readiness to advance; what would
   suggest holding or easing). Include the *uncertainty* band — when the data
   says "not enough to tell."
3. **Trend definitions** — how (or whether) to read `mood_checkin` and completion
   over time, and how to avoid pathologising ordinary day-to-day variance.
4. **Framing review (Decision 7.4)** — review our wording so an indicator is
   never presented as clinical measurement, a diagnosis, a mastery-of-condition
   claim, or a therapeutic outcome (CONTENT_SAFETY.md §3). It is an *engagement /
   independence indicator for your judgment*, nothing more.
5. **Suggestion content & tone** — when a signal is present, what a *suggestion*
   to update the (therapist-owned) premise should look like, so it reads as a
   prompt for your decision, not an instruction.

## Guarantees we make to you (so the boundaries are explicit)

- **You decide; the system suggests.** It never edits a premise, generates a
  story, or schedules one on its own (Decisions 3/8). Every suggestion lands with
  you to accept, edit, or dismiss.
- **Every accepted change re-enters the full safety pipeline** — generation →
  scene-script validation → content-safety → human review — before it reaches the
  child (Decision 4). Progress is never a bypass.
- **The data is special-category child data.** It is minimised, encrypted at
  rest, never used to train a model, and verifiably hard-deleted with the child's
  other artifacts on request (Decision 5; PRIVACY.md §5/§6/§7).
- **No black box.** The measure will be deterministic and will always show you
  the exact sessions and values behind it (Decision 2).

## What happens after you respond

Your definitions (K, thresholds, trends, framing, suggestion tone) get recorded
against ADR-002 Decision 7.1, and only then does the progress **measure** get
built — as configuration you own, not constants engineering chose. Until then the
engine stays gated; the evidence view and the accept/edit/dismiss plumbing exist
but compute no measure and generate no suggestion.

## Open questions for you

- Is a per-goal window the right unit, or should signals be per-behaviour within
  a goal?
- Should "not enough data" be a first-class state that suppresses any suggestion?
- Are there goals or contexts where progress-suggestion should be **off** by
  default (e.g. regulation/mood goals vs. concrete routines)?
