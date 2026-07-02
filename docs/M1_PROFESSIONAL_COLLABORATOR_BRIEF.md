# M1 progress engine — brief for the professional collaborator

**Status:** Draft v0.2 (2026-07-01) · **For:** a trained therapist / professional
collaborator (ADR-002 Decision 7.1) · **Owner:** WeGoFwd2020 · **Design:**
`docs/ADR_003_progress_engine_design.md`

> **To author the policy:** the concrete file format, field-by-field, is in
> `docs/PROGRESS_POLICY.md`, with a fill-in-the-blanks starter at
> `docs/examples/progress_policy.template.json` (ships inert — `enabled: false`).
> This brief is the *why*; that doc is the *how*.

> ADR-002 deliberately leaves the *clinical judgment* out of engineering's hands.
> The progress engine may not be built until a trained professional defines what
> counts as a meaningful signal. This brief states exactly what we need from you,
> and — just as important — what we will **not** do with it.
>
> Since v0.1 we have **designed the engine (ADR-003)** and **built its mechanics**
> — the schema and the deterministic interpreter — so your definitions now plug
> into a concrete, ready shape rather than a to-be-designed one. Crucially, the
> engine ships **no thresholds and no defaults**: it cannot run until *you* supply
> them. Your answers below become a **`ProgressPolicy`** — configuration you own,
> not constants engineering chose (ADR-003 Decision 2). Nothing runs against real
> data until the ADR-002 Decision 7 gate is fully open.

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

## The quantities a signal can be built from (ADR-003)

ADR-003 gives the engine a small, fixed set of **transparent, deterministic
quantities** computed from the raw fields above, over the window. These are the
only building blocks a rule can test — each is a plain arithmetic summary, never a
score or a verdict:

- **independence rate** — share of the window's sessions that were `independent`.
- **completion rate** — share where `completed` was yes.
- **refusal rate** — share that were `refused`.
- **mean mood** — average of the `mood_checkin` values (1–5).
- **mood trend** and **completion trend** — the newer half of the window minus the
  older half (a simple "getting better / worse" signed difference; needs at least
  two sessions).

Your job is **not** to invent these quantities — it is to say *which* of them
matter, in *what* combination, and at *what* value. If a signal you have in mind
needs a quantity that is not on this list, tell us: adding one is a deliberate,
reviewable change, not something we improvise.

## What we need you to define (Decision 7.1)

Engineering will **not** pick these — they are clinical judgment. Each maps to a
field of the `ProgressPolicy` the engine reads (ADR-003), noted in *italics*:

1. **Window K** — how many recent sessions a signal should consider. *(policy
   `window`.)* The built engine currently reasons over a fixed **count** of recent
   sessions; if you need a *time* window (e.g. "the last 3 weeks") as well, say so —
   it is an extension we would add deliberately.
2. **The uncertainty floor** — the fewest sessions before the engine says anything
   at all; below it, the verdict is "not enough to tell" and no suggestion is made.
   *(policy `min_sessions`.)*
3. **Thresholds** — what pattern, over K, constitutes a meaningful signal, built as
   one or more **rules**. A rule is a set of conditions on the quantities above
   (e.g. *independence rate ≥ 0.8 **and** completion rate ≥ 0.8 → "ready to
   advance"*); all conditions in a rule must hold, and rules are tried in your order.
   Include the patterns that should suggest **holding** or **easing**, and the
   ones that should stay silent. *(policy `rules`, each a `ThresholdRule` of
   `Condition`s.)*
4. **Trend definitions** — whether to read the mood/completion **trend** quantities
   at all, and at what magnitude a change is meaningful rather than ordinary
   day-to-day variance. *(trend conditions inside your rules.)*
5. **Framing review (Decision 7.4)** — review our wording so an indicator is
   never presented as clinical measurement, a diagnosis, a mastery-of-condition
   claim, or a therapeutic outcome (CONTENT_SAFETY.md §3). It is an *engagement /
   independence indicator for your judgment*, nothing more.
6. **Suggestion content & tone** — for each rule that should surface a suggestion,
   the exact premise wording and the short rationale, so it reads as a *prompt for
   your decision, not an instruction*. The engine uses your words **verbatim** and
   writes none of its own; a rule may also fire as a silent signal with no
   suggestion. *(a rule's `suggested_premise` and `rationale`.)*

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

Your definitions (window, floor, rules, trends, framing, suggestion copy) are
written up as the first **`ProgressPolicy`** and recorded against ADR-002 Decision
7.1. Because the engine's mechanics are already built (ADR-003), there is no new
measure to construct — your policy is loaded into the deterministic interpreter
that already exists, and *that* is the moment it can first run. Even then it stays
gated until the rest of Decision 7 is satisfied — your framing sign-off (7.4) and
the DPIA touchpoint for profiling a child (7.6). The evidence view and the
accept / edit / dismiss plumbing are live; the measure and suggestions produce
nothing until your policy is loaded.

## Open questions for you

ADR-003 settled two of the v0.1 questions *structurally* — the design now bakes them
in, but the values are still yours:

- "Not enough data" **is** a first-class state that suppresses any suggestion
  (ADR-003 Decision 4); you set where that floor sits (`min_sessions`).
- A policy can be turned **off per goal** (`enabled`); you tell us which goals or
  contexts (e.g. regulation/mood goals vs. concrete routines) should be off.

Still genuinely open for you:

- Is a per-goal window the right unit, or should signals be per-behaviour within
  a goal?
- Do you need a **time-based** window ("last 3 weeks") in addition to a fixed
  session count, or is the count enough?
- Are there quantities missing from the fixed set above that a signal you have in
  mind would require?
