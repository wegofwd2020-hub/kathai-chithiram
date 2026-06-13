# ADR-001 — Child-perspective capture: instructional-first, experiential capture deferred behind safeguarding preconditions

**Date:** 2026-06-13
**Status:** Proposed
**Branch at decision:** main

---

## Context

Kathai Chithiram began as a parent-authored *story → animation* generator. The product
is now expanding so that a story can be authored by a **child or a parent**, viewed by the
child in a **library**, scheduled into a **daily activity plan**, and **tracked** for
progress (see README roadmap).

A distinct and therapeutically important capability sits inside this expansion: capturing a
story **from the child's perspective**. This is not a minor feature. First-person, child-POV
narration (*"I walk to the sink. I feel calm."*) is the methodologically correct form of a
social story — more effective than the third-person form used in the current prototype
(*"Silas walks to the sink"*).

"From the child's perspective," however, hides **two different captures** with very different
risk profiles:

1. **Instructional / forward-looking** — the child's voice applied to a situation they will
   face, as coaching. *"When the bell rings, I can cover my ears. I will be okay."* This is
   the classic social story.
2. **Experiential / reflective** — the child recounting what actually happened and how it
   felt. *"Today the hand dryer was too loud. I got scared and I ran."*

The experiential form invites a **vulnerable child to disclose feelings**, and in doing so
makes an implicit promise to listen. A child may reveal fear, bullying, sensory trauma,
self-harm, neglect, or that home itself is the stressor. The product is **not a clinician**
and must never act like one. Mandatory-reporting obligations and child-safeguarding duties
are legally real and vary by jurisdiction. Mishandling a disclosure harms exactly the child
the product exists to help.

Existing commitments already anticipate this but do not resolve it: `PRIVACY.md` assumes
parent-only submission (§2.1) and anticipates a DPIA (§8); `CONTENT_SAFETY.md` names a
risk-of-harm handling path as a planned item (§4), requires distress to be transformed into
supportive content rather than reproduced (§4), and mandates a human-in-the-loop review gate
(§6). None of these is yet built or tested.

This ADR records the ethical and safety **stance** before any of this is built, so that the
high-risk capability cannot be shipped casually.

## Decision

**Decision 1 — A story carries three orthogonal attributes.**
A story is modelled by `author` (parent / child / therapist), `perspective` (first- /
second- / third-person voice), and `intent` (instructional / experiential). These are
independent, not a single "story type." First-person is the **preferred output form** for
child-facing stories.

**Decision 2 — Ship instructional-first only.**
The first build supports forward-looking, first-person social stories authored by a **parent
or therapist** about a situation the child will face. This delivers most of the therapeutic
value at a fraction of the risk and is the methodologically correct form.

**Decision 3 — Defer experiential / reflective child-disclosure capture entirely.**
Capture of the child's own account of past events is **not built and not enabled** —
including no unsupervised experiential capture — until every precondition in Decision 4 is
met. Absent those, the conservative default stands: the feature does not exist.

**Decision 4 — Hard preconditions before experiential capture may be built or enabled.**
All of the following must be satisfied and recorded:
1. A written **risk-of-harm / safeguarding protocol** designed *with* a qualified
   child-safeguarding professional or therapist and reviewed by **legal counsel** (mandatory
   reporting differs by jurisdiction).
2. The **DPIA** anticipated in `PRIVACY.md` §8 is completed.
3. A **confidentiality model** is decided deliberately and humanely with professional input —
   specifically whether a child may hold content the parent does not automatically see, and
   how a disclosure implicating a caregiver is handled. This must be an explicit decision,
   never an accidental fall-out of the data schema.
4. **Human-in-the-loop is the *right* human.** For ordinary content a parent reviews; for a
   possible disclosure the reviewer is equipped for it — not "whoever holds the account." The
   review path is tested before launch.
5. **Do-no-harm on playback** is enforced: never auto-render or auto-play a child's
   distressing account back to them; a trusted adult previews first; distress is transformed
   to supportive per `CONTENT_SAFETY.md` §4.
6. **No clinical pretense** — no diagnoses, no therapeutic promises (`CONTENT_SAFETY.md` §3).

**Decision 5 — Automation is never the sole safeguard.**
The LLM and the automated pipeline are never the only thing standing between a child's
disclosure and a safe human response. Any design that relies on the model to triage child
harm is rejected.

**Decision 6 — Developed in partnership with a trained professional.**
The experiential track, including its safeguarding protocol, is developed *with* a trained
professional/therapist as a named collaborator. This is a precondition of the work, not a
review afterthought.

## Consequences

### Positive
- The highest-risk capability cannot ship before its safeguards exist; the stance is durable
  and reviewable rather than living only in chat.
- The instructional-first product is both safe and the methodologically stronger form, so the
  near-term roadmap loses little value.
- Privacy and safety obligations (`PRIVACY.md` §4/§8, `CONTENT_SAFETY.md` §4/§6) gain a
  concrete sequencing and an owner outside engineering.

### Negative
- Experiential capture — a genuinely valuable "the child is heard" feature — is deferred,
  possibly for a long time, and depends on external professional and legal engagement.
- The three-attribute story model and first-person narration add scope to the scene-script
  contract and the `wegofwd-llm` prompt now, ahead of the experiential payoff.

### Neutral
- A confidentiality model must eventually be chosen; this ADR forces the choice to be
  deliberate but does not make it.
- Establishes the ADR convention (`docs/ADR_NNN_<slug>.md`) for this repo.

## Alternatives considered

- **Build both tracks together now** — rejected: ships the highest-risk capability before any
  safeguarding protocol, DPIA, or tested review path exists.
- **Never capture the child's perspective at all** — rejected: forgoes the first-person form
  that is the methodological gold standard. The *instructional* first-person form is safe and
  high-value; only the *experiential* form carries the disclosure risk.
- **Rely on the LLM / automated moderation to handle disclosures** — rejected (Decision 5):
  not an appropriate sole safeguard for child harm.
- **Default to "parent sees everything" for experiential content** — rejected as an *implicit*
  default: a child may disclose something about a caregiver. The confidentiality model must be
  a deliberate, professionally-informed decision (Decision 4.3).

## Migration / rollout

No code yet exists for this; the ADR records a stance before build.

- **Instructional track (now):** extend `docs/SCENE_SCRIPT_CONTRACT.md` with `author`,
  `perspective`, and `intent` fields; add first-person narration grammar to the `wegofwd-llm`
  generation prompt; keep the human review gate (`CONTENT_SAFETY.md` §6).
- **Doc updates:** revise `PRIVACY.md` (parent-only assumption → multi-actor authoring) and
  `CONTENT_SAFETY.md` to reference this ADR and the deferral.
- **Experiential track (gated):** tracked separately; cannot begin until the Decision 4
  preconditions are satisfied. Revisit this ADR to record each gate as it is met before any
  status change.
- **Partner engagement:** identify and engage a trained professional/therapist as the named
  collaborator (Decision 6) before experiential design starts.

Status flips `Proposed → Accepted` only once the instructional-track contract/doc changes land
and the deferral is reflected in `PRIVACY.md` / `CONTENT_SAFETY.md`. Do not pre-flip.
