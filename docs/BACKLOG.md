# Kathai Chithiram — Backlog

Lightweight capture of deferred work so intent isn't lost. Not a spec.

## Milestones

- **M1 · Per-child progress quantification → therapist-suggested premise customization** — quantify each child's feedback (part c) into a progress measure (e.g. % independent over last K sessions, mastery flag, regulation trend) that may *suggest* — never auto-author — an updated premise (part a) for future stories. The therapist decides; the safety gate still runs (ADR-001 Decision 5). **Stance ADR: `docs/ADR_002_progress_quantification_premise_suggestion.md` (Accepted)** — capture-first, suggestion-only, engine deferred behind preconditions; the capture-track primitive schema has landed. **Engine-design ADR: `docs/ADR_003_progress_engine_design.md` (Proposed)** — a deterministic, policy-driven measure + suggestion seam where the clinical parameters (window K, thresholds, trends) are collaborator-authored `ProgressPolicy` configuration, never engineer-chosen constants; the mechanics are buildable now but stay gated off until the ADR-002 Decision 7 preconditions are met. *Feedback primitives (`prompt_level` refused/prompted/independent, `completed`, `mood_checkin`) keyed to a structured `goal` id already accrue; the evidence view and accept/edit/dismiss path exist and compute no measure.*
