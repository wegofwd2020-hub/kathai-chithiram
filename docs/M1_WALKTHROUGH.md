# M1 progress engine — end-to-end walkthrough (synthetic data)

> **This is a demonstration with synthetic data — not clinical guidance.** Every
> threshold and every line of premise copy below is an **illustrative placeholder**,
> and the session feedback is **fabricated** (no real child). It shows how the loop
> *works*; it says nothing about what a real signal should be. A trained therapist / OT
> authors the real policy (`docs/PROGRESS_POLICY.md`, ADR-002 Decision 7.1); production
> use also needs the clinical-copy sign-off (D7.4) and the DPIA progress-profiling
> touchpoint (D7.6). The repo ships a **self-labeling enabled sample**
> (`docs/examples/progress_policy.sample.json`, id + copy marked `SAMPLE … not
> clinical`) for demos/dev; the fill-in **template** for real use
> (`docs/examples/progress_policy.template.json`) stays `enabled: false`.

The loop has three CLI steps: **run** the engine (`kc progress`), **see** what it
proposed (`kc suggestions`), **decide** on it (`kc decide`). Below, one run produces a
suggestion a therapist accepts; two others show the engine *declining* to suggest.

## 0. A sample policy

A ready-to-run **sample** ships at
[`docs/examples/progress_policy.sample.json`](examples/progress_policy.sample.json) —
`enabled: true`, with `policy_id` `SAMPLE-not-clinical-do-not-use-in-production` and
`[SAMPLE - not clinical]` baked into its premise copy, so any output it produces is
obviously not a real policy. Its thresholds are **illustrative, not clinical** — for
demos and dev only. (The fill-in **template** for the real thing is
`docs/examples/progress_policy.template.json`, which ships `enabled: false`.)

The commands below use the sample; swap in the collaborator's authored policy for real
use (`docs/PROGRESS_POLICY.md`).

## 1. Seed a story + therapist grant + synthetic feedback

Session feedback normally accrues through the capture track (ADR-002); here we write a
few synthetic records straight to the store. In a Python shell (with the package
installed):

```python
from datetime import datetime, timezone
from kathai_chithiram.storage import StoryArtifactStore
from kathai_chithiram.feedback.schema import SessionFeedback, PromptLevel, MoodCheckin

store = StoryArtifactStore("kc_store_demo")
store.create_story("story-A", created_at=datetime(2026, 6, 1, tzinfo=timezone.utc), story_text="x")
store.write_grants("story-A", {"owner_id": "local-operator", "assignments": {"ot-jane": "therapist"}})

for day in range(5):  # 5 independent, completed sessions on the goal
    store.append_session_feedback("story-A", SessionFeedback(
        goal_id="goal-brush", story_id="story-A",
        prompt_level=PromptLevel.INDEPENDENT, completed=True, mood_checkin=MoodCheckin.HAPPY,
        recorded_at=datetime(2026, 6, 1 + day, tzinfo=timezone.utc),
    ).to_record())
```

## 2. Run the engine — `kc progress`

The acting principal must hold the **therapist** role on the story (it fails closed
otherwise). Set `KC_PRINCIPAL` to the granted id:

```
$ KC_PRINCIPAL=ot-jane kc progress goal-brush --policy docs/examples/progress_policy.sample.json \
      --story story-A --store-root kc_store_demo

goal: goal-brush  |  policy: SAMPLE-not-clinical-do-not-use-in-production
sessions in window: 5/6  |  state: signal_present
fired rule: advance  |  signal: advance
metrics (raw, explainable):
  independence_rate: 1.000
  refusal_rate: 0.000
  completion_rate: 1.000
  mean_mood: 4.000
  ...
recorded suggestion <id> on story story-A — INERT, awaiting a therapist decision.
```

The `advance` rule matched (independence ≥ 0.8, refusal ≤ 0.1), so a suggestion was
**recorded**. Recording is the only effect — nothing is generated or delivered.

## 3. See it — `kc suggestions`

```
$ KC_PRINCIPAL=ot-jane kc suggestions story-A --store-root kc_store_demo

1 open suggestion(s) for story-A:

  <id>  (goal goal-brush)
    premise: [SAMPLE - not clinical] Introduce a slightly longer version of the same routine.
    why:     [SAMPLE - not clinical] Independence has held across recent sessions with low refusal.
```

## 4. Decide — `kc decide`

The therapist accepts as-is, edits the wording, or dismisses:

```
$ KC_PRINCIPAL=ot-jane kc decide story-A <id> --accept --reviewer ot-jane --store-root kc_store_demo
✓ Recorded accepted on <id> by ot-jane.
(The approved premise re-enters the full safety pipeline before any new story is made — ADR-002 D4.)
```

`kc suggestions` now shows none — the suggestion is decided. (`--edit --premise "…"`
records an edited premise; `--dismiss` closes it with no premise.)

## The engine declines when it should

Two contrasting runs (seed each on its **own goal id** — see the note below):

- **A child refusing** (5 refused sessions on `goal-refuse`):
  ```
  state: signal_present   fired rule: hold   refusal_rate: 1.000
  no suggestion produced (the state/rules did not warrant one).
  ```
  The `hold` rule fires but carries **no copy**, so it signals *without* suggesting.
- **Too little data** (2 sessions, `min_sessions` is 4):
  ```
  sessions in window: 2/6   state: insufficient_data
  no suggestion produced.
  ```

So the engine only proposes a premise when a clinician-authored rule **with copy**
fires on **enough** data.

## Things worth knowing

- **Evidence is per goal, across all of a child's stories** (`build_goal_evidence`).
  The `--story` argument only says *where the suggestion is filed* — the signal reflects
  the child's whole history on that goal, not a single story.
- **Metrics are transparent** (rates, means, half-window trends) and ride along on every
  verdict, so a therapist can see *why* — the number behind a suggestion, not a black box.
- **Inert by design.** The engine never edits a premise, generates a story, or schedules
  one (ADR-002 D3/4/8). A therapist decides; an accepted premise still goes through
  content-safety validation and the human-review gate before any child sees a new story.

## Going live (for real)

Replace the sample with the collaborator's authored policy per `docs/PROGRESS_POLICY.md`
— their window K, thresholds, and premise/rationale wording — set `enabled: true` after
their clinical-copy review (D7.4) and the DPIA touchpoint (D7.6), and run the same three
commands against real, consented feedback.
