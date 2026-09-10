# ADR-007 — Scene-script v2: a closed art vocabulary and a machine-checkable authoring grammar

**Date:** 2026-09-10
**Status:** Proposed
**Branch at decision:** main

---

## Context

The v1 contract is strict where it is cheap and silent where it matters.

`SCENE_SCRIPT_SCHEMA_V1` sets `additionalProperties: False` at all four levels, enumerates
`transition_in`/`transition_out` to `("cut", "fade", "dissolve")`, bounds `duration_s` to
2–8 s, `fps` to 8–30, captions to 140 characters, and forces `child_token` to an uppercase
shape so a lowercase real name is structurally excluded. `validation.py` then adds four
cross-field rules and reconstructs every error message from the *schema* side so an
offending caption is never logged. That is careful, well-tested work.

But the five fields that decide what the child actually **sees** are unconstrained strings:

| Field | v1 type | What the renderer does with it |
|---|---|---|
| `setting` | `string`, `minLength: 1` | `scene_art_hints._BACKGROUND_KEYWORDS` substring-matches; no match → `Background.CALM` |
| `props[]` | `string` | `generate_animation._PROP_DRAW` substring-matches ~19 names, draws at most 2; unrecognised **silently skipped** |
| `characters[].pose` | `string`, `minLength: 1` | `_POSE_GESTURES` maps four words to `Gesture.WAVE`; everything else → `Gesture.REST` |
| `characters[].expression` | `string`, `minLength: 1` | `_EXPRESSION_WORDS` maps ~28 words to four `Expression` members; no match → falls through to caption keywords |
| `audio.sfx[]` | `string` | opaque cue labels resolved against a local sound bank |

The complete renderable vocabulary is therefore **six backgrounds, four expressions, two
gestures and about nineteen props** — and none of it is written down anywhere the generator
can see. The result is a system in which a model asks for "a busy supermarket aisle with a
shopping trolley," the contract accepts it, the validator passes it, and the child watches
a stick figure standing in a blank calm room. `resolve_figure_cues` is a well-judged
mitigation (script-first, caption-fallback, so a generic authored value never suppresses a
clear caption) but it is compensating for a contract that does not state its own limits.

Three consequences follow, and they are the reason this ADR precedes any model work:

1. **A model cannot learn a vocabulary that is never stated and never enforced.** No amount
   of fine-tuning fixes an unstated action space. Under grammar-constrained decoding
   (ADR-006 L1) an enumerated vocabulary becomes *unmissable*: an undrawable value is not
   merely rejected, it is unrepresentable.
2. **Silent degradation is a safety-adjacent failure in this product.** For a child using a
   visual schedule, a background that does not match the narration is not a cosmetic miss;
   it is the story failing to do the one thing it exists to do. The system's own discipline
   everywhere else — `validate_scene_script` rejects rather than repairs, `guard_render`
   deletes the draft rather than promoting it — is violated here alone.
3. **The clinical grammar of a social narrative is absent from the contract.** ADR-001 D1
   decided that a story carries `author`, `perspective` and `intent`, and D2 chose the
   instructional-first, first-person track. None of it is in the schema; the contract is
   still third-person-shaped and the prompt asks for first person in prose. Nothing checks
   it.

This ADR closes all three, and does so **without engineering choosing a single clinical
value** — following ADR-003 D2's rule that engineering ships the interpreter and never the
numbers.

## Decision

**Decision 1 — Promote the renderable vocabulary into the contract as closed enums,
generated from one registry.**
A new `scene_script/vocabulary.py` is the single source of truth for `Background`,
`Expression`, `Gesture`, `Prop` and `SfxCue`. `SCENE_SCRIPT_SCHEMA_V2` derives its `enum`
lists from that registry, and `rendering/scene_art_hints.py` derives its lookup tables from
the same registry rather than holding a parallel copy. Keyword inference does not
disappear — `generation/scene_builder.py`'s offline and `kc author` paths still *infer* a
value from a caption — but inference now resolves to a registry member or fails, instead of
producing a string that only sometimes means something.

**Decision 2 — An unrecognised art value becomes a rejection, not a silent default.**
This is the substantive behavioural change. `props` entries the renderer cannot draw, and
`setting`/`pose`/`expression` values outside the enum, currently pass validation and vanish
at render time. In v2 they fail `validate_scene_script` under new rule ids
(`scene.setting.unknown`, `scene.props.unknown`, `scene.character.pose.unknown`,
`scene.character.expression.unknown`, `scene.audio.sfx.unknown`), reported the same
log-safe way as every other rule — rule id, scene index, field name, never the value.
Under ADR-006's repair loop a rejection is a *corrective signal*; under constrained
decoding it never arises. Silent degradation gives the model neither.

**Decision 3 — Every registry member must be drawable by every registered renderer, and a
test says so.**
`tests/…/rendering/test_conformance.py` already parametrises over `ALL_RENDERERS` and
asserts each declares MAJOR 1 and rejects an invalid script before touching matplotlib or
`bpy`. It gains a vocabulary axis: for each renderer × each enum member, the renderer must
report the member as drawable. Adding a `Prop` to the registry without adding art therefore
breaks the build. This is the mechanism that keeps "what the model may ask for" and "what
the child can see" identical by construction, and it is what makes it safe to grow the
vocabulary later — growth becomes an art task with a failing test as its definition of done,
not a coordination problem.

**Decision 4 — Add ADR-001's `author`, `perspective`, `intent` at the top level, and
constrain the instructional track.**
`author ∈ {parent, therapist}` (ADR-001 D3 defers child authorship entirely; the enum omits
it rather than accepting-and-refusing it), `perspective ∈ {first_person, second_person,
third_person}`, `intent ∈ {instructional, experiential}`. A cross-field rule enforces
ADR-001 D2: `intent = "experiential"` is **rejected outright** (`story.intent.gated`) until
ADR-001 D4's six preconditions are met, and the instructional track requires
`perspective = "first_person"`. Encoding the gate in the contract rather than in a prompt
means the deferral survives a prompt edit, a provider swap and a fine-tune.

**Decision 5 — Add a per-scene `sentence_function`, and make the ratio a policy, not a
constant.**
Each scene declares `sentence_function ∈ {descriptive, perspective, coaching,
affirmative}` — describing a situation, naming an internal state, directing a behaviour, or
reassuring. The generic social-narrative literature holds that a story should describe far
more than it directs, and expresses this as a minimum ratio of non-coaching to coaching
sentences.

**Engineering ships the counter; the clinician ships the ratio.** A
`NarrativePolicy` — deliberately shaped like `progress/policy.py`'s `ProgressPolicy` —
carries `policy_id`, the minimum non-coaching:coaching ratio, an optional maximum
`caption_chars` below the contract's hard 140 ceiling, and an optional maximum scene count.
There is **no `DEFAULT_RATIO`** and no fallback anywhere in the package, for the same reason
`progress/policy.py` has no `DEFAULT_K`: an engineer's guess about how much a child should
be told what to do must not be able to reach a child by omission. With no policy supplied,
`sentence_function` is recorded and the ratio is not enforced.

**Decision 6 — Reading load is clinical; 140 characters is merely technical.**
`MAX_CAPTION_CHARS = 140` is a rendering and layout limit. How much text a particular
child's story should carry is a clinical judgement, so `NarrativePolicy.caption_chars` may
lower it per programme and may never raise it. Same shape as Decision 5; same reason.

**Decision 7 — v2 is additive and v1 keeps rendering.**
`SUPPORTED_MAJOR_VERSION` becomes a supported *set* `{1, 2}`; `SceneScriptRenderer.
supported_majors` becomes `frozenset({1, 2})` and the conformance suite runs both axes.
v1 scripts already on disk validate and render unchanged, with the new rules inapplicable.
Generation emits v2 from the day the registry lands. A future ADR may retire v1; this one
does not, because stored scripts belong to families and a contract change must not strand
them. The new top-level fields (Decision 4) and `sentence_function` are **required in v2**,
which is what makes them enforceable — `additionalProperties: False` means there is no
gradual-adoption path in-major, and that is the correct trade.

**Decision 8 — Naming: use "social narrative" in product copy and code.**
**Social Stories™ is a registered trademark** (Carol Gray; registered to Gestalt
Perspective LLC), and the term denotes a specific methodology with its own defining
criteria and training. `README.md` and `generation/system_prompt.py` currently use "social
stories" descriptively. For a commercial product this is a cheap risk to remove and an
expensive one to leave: switch outward-facing and code-facing language to **"social
narrative"**, keep any Social Stories™ claim for a properly licensed or trained
relationship, and let the clinical collaborator decide whether pursuing that relationship
is worth it. The rubric this ADR enables is *informed by* the published literature and
authored by our collaborator; it must not be presented as an implementation of someone
else's named method.

## Consequences

### Positive

- The model's action space becomes finite, stated and enforced — the precondition for both
  constrained decoding and any useful fine-tune, and the single largest quality lever
  available without a GPU.
- Silent degradation is eliminated at its source. The system's existing "reject, never
  repair, never quietly proceed" discipline finally covers the fields the child actually
  sees.
- The vocabulary conformance test converts "make the animations better" from an open-ended
  aspiration into a bounded, testable backlog: add a member, watch the build go red, draw
  the art, watch it go green.
- ADR-001's decided-but-unbuilt attributes become real, and its deferral of experiential
  capture becomes structurally enforced rather than prompt-enforced.
- The clinical judgement in the system stays in a reviewable, versioned, collaborator-
  authored artefact — legible to a clinician, a DPO or a parent — rather than diffusing
  into weights. This is what makes ADR-006's model programme defensible.

### Negative

- v2 requires new top-level and per-scene fields, so every generation path
  (`generator.py`, `offline.py`, `scene_builder.py`, `authoring/template.py`) and both
  reference renderers change together. This is the largest single migration the contract
  has had.
- A closed vocabulary is a smaller expressive space than free text. Some parent stories
  will not map cleanly, and the honest failure mode is a rejection where v1 produced a
  plausible-looking but wrong animation. That is the intended trade, and it makes the
  vocabulary's *size* a product priority rather than an afterthought.
- Two supported majors means two schema documents, two prompt variants and a doubled
  conformance matrix until v1 is retired.
- `NarrativePolicy` adds a second collaborator-authored artefact alongside `ProgressPolicy`.
  Two policies with no defaults is more to explain and more to get authored; a single
  combined artefact was considered and rejected (below).

### Neutral

- The size of the initial v2 vocabulary is not fixed here. It should start at exactly what
  the renderers draw today, so the registry lands green, and grow on demand.
- Whether `sentence_function` is generated by the model or derived by a classifier over the
  narration is an implementation choice; the contract only requires that it be present and
  correct, and a validator can disagree with a claimed label.

## Alternatives considered

- **Leave the fields free-form and improve the prompt.** Rejected: it is the status quo,
  and the failure is invisible — nothing in the system currently reports that a scene
  rendered as a blank calm room, so the defect cannot even be measured.
- **Keep free-form fields but emit a warning on an unrecognised value.** Rejected: the
  repository has a precedent for advisory signals (`minimization_warnings`) and reserves
  them for cases where blocking a parent would be disproportionate. A wrong picture in a
  child's story is not that case, and a warning nobody reads is degradation with paperwork.
- **Free-form fields plus an embedding-nearest-neighbour snap to the closest drawable
  value.** Rejected: it reintroduces silent substitution with a stochastic component, is
  untestable at the boundary, and would let "supermarket" become "kitchen" with no record.
- **Put the ratio and caption limits in the schema as constants.** Rejected on ADR-003 D2
  grounds. A hard-coded ratio is an engineer making a clinical decision by omission, which
  is the exact failure `progress/policy.py`'s "there is no `DEFAULT_K`" docstring was
  written to prevent.
- **One combined clinical policy artefact covering progress and narrative.** Rejected for
  now: `ProgressPolicy` is gated behind ADR-002 D7 and `NarrativePolicy` is not, so merging
  them would drag an ungated capability behind a gate. Revisit if a collaborator finds
  authoring two files a genuine burden.
- **Bump to v1.1 rather than v2.** Rejected: `additionalProperties: False` plus required
  new fields is a breaking change by construction, and `validation._check_supported_version`
  gates on MAJOR. Calling a breaking change a minor bump would defeat the version gate the
  renderer relies on.

## Migration / rollout

- **Not yet started.** Proposed; nothing has landed.
- **Ratification condition (Proposed → Accepted):** the vocabulary registry and the
  conformance-matrix test merged green with the v2 schema, `SUPPORTED_MAJOR_VERSION`
  widened, and a `NarrativePolicy` **template** shipped in `docs/examples/` with
  `enabled: false` and `policy_id: "TEMPLATE-replace-me"`, mirroring
  `progress_policy.template.json`. Ratification does **not** require a clinician-authored
  policy to exist — that is the enabling step, not the design step, exactly as ADR-003 D7
  separates them.
- **Order of work:** (1) `scene_script/vocabulary.py` registry + conformance matrix against
  today's art, no schema change; (2) `SCENE_SCRIPT_SCHEMA_V2` deriving enums from it, new
  rule ids, `SUPPORTED_MAJOR_VERSION = frozenset({1, 2})`; (3) generation paths emit v2;
  (4) `author`/`perspective`/`intent` + the `intent.gated` rule; (5) `sentence_function` +
  `NarrativePolicy` + `docs/NARRATIVE_POLICY.md` authoring guide; (6) rename to "social
  narrative" across `README.md`, `system_prompt.py`, `BRAND.md` and parent-facing copy.
  Steps 1–3 are independently shippable and carry most of the value.
- **Tickets:** `KC-13` covers steps 1–4; `KC-16` covers step 5; the rename (step 6) is a
  standalone chore with a legal note attached.
- **Docs to revise:** `docs/SCENE_SCRIPT_CONTRACT.md` (a v2 section beside v1),
  `docs/CONTENT_SAFETY.md` §5 (enforcement point 2 gains vocabulary and grammar rules),
  `docs/STORY_TEMPLATE.md` (the template gains the new fields), `docs/BRAND.md` (naming),
  `README.md`.
- **Tests, mock data only:** every enum member drawable by every renderer; an unknown value
  in each of the five fields rejected under its own rule id and **logged without the
  value** (extending `test_overlong_caption_does_not_leak_text`'s pattern); a v1 fixture
  from `mock_scripts.py` still validating and rendering; `intent: "experiential"` rejected;
  a v2 script with a coaching-heavy scene set rejected under a supplied `NarrativePolicy`
  and accepted with none supplied.
- **Explicitly out of scope:** growing the vocabulary itself. This ADR builds the mechanism
  and lands it at parity with today's art; what to draw next is a product and clinical
  question, informed by which rejections families actually hit.
