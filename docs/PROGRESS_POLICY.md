# Authoring a ProgressPolicy (for the professional collaborator)

The M1 progress engine ships **no clinical values**. It runs only a policy **you** — a
trained therapist / OT — author. This is deliberate (ADR-002 Decision 7.1, ADR-003
Decision 2): an engineer's thresholds must never reach a child, so the code has no
defaults and cannot run until you supply a policy.

This page is how to write that policy. A starting file is at
[`docs/examples/progress_policy.template.json`](examples/progress_policy.template.json)
— **copy it and replace every value.** The template's numbers and wording are
illustrative placeholders, **not** clinical judgment, and it ships `"enabled": false`
so it does nothing until you deliberately turn it on.

## What the engine does with your policy

For a goal, it looks at the child's most-recent **K** sessions of feedback (prompt
level, completion, mood), computes a few transparent metrics, and — if a rule you
wrote matches — records a **suggestion** for you to review. It never edits a premise,
generates a story, or decides anything: **you** accept / edit / dismiss each suggestion
(`kc decide`), and an accepted premise still goes through the full safety pipeline and
human review before any child sees it.

## The fields

| Field | Meaning | You set |
|---|---|---|
| `policy_id` | A version label recorded on every suggestion so it's traceable | a name/version |
| `window` (K) | How many most-recent sessions to reason over (≥ 1) | **your K** |
| `min_sessions` | Fewest sessions before it says anything but "not enough data" (1…window) | **your floor** |
| `enabled` | On/off. **Ships `false`; set `true` only after your review** | `true` when ready |
| `rules` | Tried in order; the **first** whose conditions **all** hold fires. May be empty | **your rules** |

Each **rule**:

| Field | Meaning |
|---|---|
| `rule_id` | Opaque id, unique in the policy (recorded as the fired rule) |
| `conditions` | A list; **all** must hold (logical AND). Express "or" as separate rules |
| `signal` | A short label the engine records (e.g. `advance`, `hold`) |
| `suggested_premise` + `rationale` | The premise to propose and why — **your clinical wording**. Set **both or neither**: a rule may signal *without* suggesting. No child identifiers in the text |

Each **condition** is `{ "metric", "comparator", "threshold" }`.

- **`metric`** — one of the fixed vocabulary, each with a valid threshold range:

  | Metric | What it is | Range |
  |---|---|---|
  | `independence_rate` | Fraction of window sessions done independently | 0.0–1.0 |
  | `completion_rate` | Fraction completed | 0.0–1.0 |
  | `refusal_rate` | Fraction refused | 0.0–1.0 |
  | `mean_mood` | Mean of the 1–5 mood check-ins | 1.0–5.0 |
  | `mood_trend` | Newer-half mean mood minus older-half (needs ≥ 2 sessions) | −4.0–4.0 |
  | `completion_trend` | Newer-half completion rate minus older-half (needs ≥ 2) | −1.0–1.0 |

- **`comparator`** — `>=`, `>`, `<=`, `<`.
- **`threshold`** — a number **within** that metric's range (an out-of-range value is
  rejected as a typo).

## How to run it

Once you've filled the template and set `"enabled": true`, hand the file over; it runs
as the therapist assigned to the story:

```bash
kc progress <goal-id> --policy your_policy.json --story <story-id>
kc suggestions <story-id>
kc decide <story-id> <suggestion-id> --accept | --edit --premise "…" | --dismiss --reviewer NAME
```

## Before it goes live

Enabling this in production also needs your **clinical-copy / framing sign-off** (D7.4)
and the **DPIA progress-profiling touchpoint** (D7.6). Until then, keep `enabled: false`
or run only against synthetic data. The full context is in
`docs/M1_PROFESSIONAL_COLLABORATOR_BRIEF.md`, `docs/ADR_002_progress_quantification_premise_suggestion.md`,
and `docs/ADR_003_progress_engine_design.md`.
