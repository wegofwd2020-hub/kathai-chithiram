# KC-13 — Scene-script v2: closed art vocabulary registry + reject unknown values

**Labels:** P1, quality, contract
**Status:** 📋 Proposed — **do this first**; KC-12, KC-14 and KC-16 all depend on it
**Refs:** `docs/ADR_007_scene_script_v2_authoring_grammar.md` D1–D4; `docs/ADR_006_domain_model_strategy.md` L0; `scene_script/schema.py`, `scene_script/validation.py`, `rendering/scene_art_hints.py`, `generation/scene_builder.py`, `generate_animation.py`, `blender_animation.py`, `tests/kathai_chithiram/rendering/test_conformance.py`

## Why
Five contract fields decide what the child actually sees, and all five are unconstrained
strings: `setting`, `props[]`, `characters[].pose`, `characters[].expression`,
`audio.sfx[]`. The renderer keyword-matches them and **silently degrades** — an unmatched
setting becomes `Background.CALM`, an unmatched pose becomes `Gesture.REST`, an
unrecognised prop is skipped without a word. The complete drawable vocabulary is six
backgrounds, four expressions, two gestures and ~19 props, and it is written down nowhere
the generator can see.

So a story can ask for a busy supermarket, pass validation, pass the render guards, and be
delivered as a stick figure standing in a blank calm room. Nothing reports it. For a child
using a visual schedule that is not a cosmetic miss — it is the story failing at the one
thing it exists to do, and it is the only place in the system where we quietly proceed
instead of rejecting.

It is also the hard ceiling on any model work. A model cannot learn an action space that is
never stated and never enforced; under grammar-constrained decoding (KC-12) an enumerated
vocabulary makes an undrawable value *unrepresentable* rather than merely wrong.

## Acceptance criteria
- A single registry module is the source of truth for `Background`, `Expression`,
  `Gesture`, `Prop` and `SfxCue`. Both the schema's `enum` lists and
  `rendering/scene_art_hints.py`'s lookup tables derive from it; no parallel copy exists.
- `SCENE_SCRIPT_SCHEMA_V2` constrains the five fields to registry members.
  `SUPPORTED_MAJOR_VERSION` becomes a supported set `{1, 2}`, and
  `SceneScriptRenderer.supported_majors` widens to match.
- An unrecognised value **fails `validate_scene_script`** under its own rule id
  (`scene.setting.unknown`, `scene.props.unknown`, `scene.character.pose.unknown`,
  `scene.character.expression.unknown`, `scene.audio.sfx.unknown`), reported the existing
  log-safe way: rule id, scene index, field name, **never the value**.
- The renderer conformance suite gains a vocabulary axis: for every registered renderer ×
  every registry member, the renderer reports the member drawable. Adding a member without
  art breaks the build.
- The registry lands at **exact parity with the art that exists today**, so it is green on
  merge. Growing it is separate, later work.
- Every v1 script already on disk still validates and still renders unchanged; the new
  rules are inapplicable to major 1.
- Keyword inference in `generation/scene_builder.py` (offline and `kc author` paths) now
  resolves to a registry member or fails; it no longer produces a string that only
  sometimes means something.
- ADR-007's `author` / `perspective` / `intent` land at the top level, with
  `intent: "experiential"` rejected under `story.intent.gated` (ADR-001 D2/D4) and the
  instructional track requiring `perspective: "first_person"`.

## Implementation notes
- Order the work so each step is independently shippable: (1) registry + conformance matrix
  against today's art, no schema change; (2) v2 schema deriving enums from it, new rule ids,
  widened version gate; (3) generation paths emit v2; (4) the ADR-001 attributes.
- Keep `resolve_figure_cues`'s script-first / caption-fallback behaviour — it is a good
  design; it is just currently compensating for a contract that does not state its limits.
- Reuse `validation._reject` and `_safe_constraint`; the reconstruct-from-the-schema-side
  discipline (never touch `error.instance`) must extend to the new rules.
- OpenSpec docstrings; domain-specific errors, no bare `except`.
- Instrument first: before changing behaviour, count how often
  `scene_art_hints.art_hint_for` currently falls through to `Background.CALM` /
  `Gesture.REST`. That number sizes this ticket and is unknown today.
- Docs: a v2 section in `docs/SCENE_SCRIPT_CONTRACT.md` beside v1; `docs/CONTENT_SAFETY.md`
  §5 enforcement point 2; `docs/STORY_TEMPLATE.md`.

## Tests (mock data only)
- Every registry member drawable by every renderer, parametrised over `ALL_RENDERERS`.
- Each of the five fields rejected on an unknown value, under its own rule id, with a
  `caplog` assertion that the value does not appear — extending the
  `test_overlong_caption_does_not_leak_text` pattern.
- A `mock_scripts.py` v1 fixture still validates and renders end-to-end.
- `intent: "experiential"` rejected; instructional + non-first-person rejected.
- Offline and `kc author` paths emit registry-valid v2 for the shipped `docs/examples/`
  inputs.
