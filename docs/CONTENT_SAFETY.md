# Kathai Chithiram — Content Safety Guidelines

**Status:** Draft v0.1 (2026-06-11) · **Audience:** generation + rendering pipeline, reviewers.

Kathai Chithiram produces media that a **child with special needs will actually watch**. The bar for what comes out is therefore higher than for general-purpose generation. These guidelines define what generated scene scripts and animations must and must not contain, and how the pipeline enforces it.

---

## 1. Design intent

The output is a *social story* — a calm, predictable, visual narrative that helps a child understand a situation or routine. Everything below serves that intent.

## 2. MUST (every output)

- **Calm, predictable pacing.** Short scenes, simple transitions, no sudden movement, no flashing or strobing (seizure-safety: no flashes above 3 Hz, no large high-contrast oscillation).
- **Plain, concrete language.** Short sentences, literal phrasing, present tense, one idea per scene. Avoid idioms, sarcasm, and figurative language that a literal-minded child may misread.
- **Positive, supportive framing.** Show the desired behavior and a successful outcome. Narrate what *to do*, not a list of prohibitions.
- **Consistent characters.** The child-character and recurring objects stay visually consistent scene to scene (predictability is the therapeutic mechanism).
- **Captioned + narrated.** Text cards match narration so the story works with or without sound.
- **Gentle audio.** No loud, sudden, or jarring sounds; even, quiet narration.

## 3. MUST NOT (hard blocks)

- No frightening, threatening, or distressing imagery or narration (no violence, injury, punishment, abandonment, monsters, darkness-as-threat).
- No flashing/strobing or rapid scene cuts.
- No shaming or negative characterization of the child ("bad boy", "naughty").
- No medical claims, diagnoses, or therapeutic promises.
- No depiction of the child in unsafe acts presented as normal.
- No collection or display of identifying detail beyond the chosen first name/nickname.

## 4. Sensitive-input handling

Parent stories may describe distressing situations (meltdowns, fears, medical procedures, bullying). The pipeline must:

- Transform a distressing *situation* into a **supportive, resolution-oriented** story — never reproduce distress for its own sake.
- Route inputs that suggest **risk of harm** (abuse, self-harm, neglect) to a defined handling path rather than silently generating; surface an appropriate, compassionate message and resources rather than a cartoon. (Define this path with care — it concerns real children.)
- Refuse to generate when a request falls outside the product's purpose (e.g. content not aimed at helping the child understand a situation).

## 5. Enforcement in the pipeline

Safety is enforced at three points, not just trusted to the model:

1. **Generation prompt** encodes the MUST/MUST-NOT rules as system constraints.
2. **Scene-script validation** (see `SCENE_SCRIPT_CONTRACT.md`) rejects scripts that violate structural safety rules (scene length, transition type, banned content flags) *before* rendering.
3. **Render-time guards** enforce technical safety (frame-rate, flash limits, audio levels).

A script that fails validation is never rendered. Failures are logged (without raw story text) for review.

## 6. Human-in-the-loop

For the current prototype stage, a person reviews each generated story before it reaches a child. Do not remove the human review gate until automated enforcement (§5) is proven and tested.

## 7. Progress & feedback indicators (non-clinical)

Per-session feedback (`prompt_level`, `completed`, `mood_checkin`) and any progress derived from it are **engagement and independence signals for a therapist's judgment — not clinical measurement**. They are never presented as a diagnosis, an assessment of a disorder, a mastery-of-condition claim, or a therapeutic outcome (§3, "no medical claims, diagnoses, or therapeutic promises"). Any derived measure must be transparent — it shows the sessions and values behind it — and may only *suggest* a change to the therapist who decides; it never auto-authors a story, and a suggested premise still passes through the full safety pipeline (§5) and the human-review gate (§6). See `docs/ADR_002_progress_quantification_premise_suggestion.md` for the full stance; the progress engine is gated behind that ADR's preconditions. What exists today is the capture layer only — it records the raw primitives and computes nothing.

## 8. Open items (tracked as tickets)

- [x] Encode MUST/MUST-NOT rules into the generation system prompt. *(KC-4: `generation/system_prompt.py`)*
- [x] Implement scene-script safety validation (frame-rate, scene length, banned-content flags). *(KC-3: `scene_script/validation.py`)*
- [x] Implement render-time seizure-safety guards (flash/contrast/audio). *(KC-4: `rendering/safety.py`)*
- [ ] Define the risk-of-harm handling path with appropriate resources. *(ADR-001; not yet built)*
- [ ] Keep human review gate until §5 is tested. *(REMAINS — §5 is now wired end-to-end through `SceneScriptRenderer` (validate → guard before delivery) and covered by the renderer conformance suite, but the gate stays until this is proven in production)*
