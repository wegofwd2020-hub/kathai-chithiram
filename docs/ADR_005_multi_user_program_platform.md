# ADR-005 — From single-operator engine to a multi-user program platform: domain model, account-scoped access, and the privacy gate

**Date:** 2026-07-02
**Status:** Proposed
**Branch at decision:** main

---

## Context

Kathai Chithiram today is a **single-operator CLI engine**: `kc intake` / `kc generate`
turn one parent's story into a review-gated, safety-checked animation; `kc review` /
`kc assign` / `kc progress` add a review gate, per-story role grants, and the (gated) M1
progress engine. There are **no accounts, no user records, and no relationships between
people** — access is a single local `Principal` bound to a story by convention, behind
the swappable `IdentityProvider` seam ADR-004 built for exactly this moment.

The owner has articulated the product in three parts:

- **(a) Story capture → video** — a *structured, guided story template* a non-technical
  user can fill from beginning to end, which yields a scene script the existing pipeline
  renders.
- **(b) Onboarding / people** — three personas (**therapist**, **parent**, **child**);
  multiple parents of a child are grouped under a **family**; a family may have multiple
  children; **DOB is captured per persona** to build age-aware progress patterns; content
  is visible only to the **assigned therapist and the parent(s) [family]**.
- **(c) The program** — a **therapist establishes a program** for a family/child, tracks
  each child's progress, and **reports it back to parents**; program participants,
  content, and tracking are visible only to the parent/therapist.

This is a shift from *engine* to *platform*: a real **identity + family domain**, a
**program domain**, and a **parent-facing report**. Much of the substrate exists
(scene-script contract, safety, render, consent, per-story access, M1 progress
primitives), but three things do not: the story-authoring template, the people/family
entity model, and the program concept.

**One part of this materially changes what personal data we process.** `PRIVACY.md §3`
and `DPIA §3` today state we collect **only the story and the child's first name**, and
list **surname, DOB, address, school, diagnosis, biometrics, photos — and accounts — as
explicitly out of scope**, as a deliberate data-minimization stance for special-category
child data. Parts (b) and (c) introduce **accounts and DOB** and therefore *contradict
the current posture*. That is not a code decision; it is a lawful-processing decision.
This ADR records the domain shape and **gates the privacy-expanding parts behind a DPIA
revision**, mirroring the "build the seam, gate the deployment/clinical-dependent part"
pattern of ADR-002/003/004.

## Decision

**Decision 1 — Adopt the three-part product shape, but sequence it by data risk, not by
feature order.** (a) the story template adds **no new personal data** and is buildable
now; (b) identity + DOB + accounts and (c) programs + reporting **expand special-category
processing** and are gated on Decision 7. The engine is not rebuilt — these are new
layers above the existing contract/render/progress core, reached through existing seams.

**Decision 2 — A minimal people/family domain model.** Entities and relationships:

- **Family** — the unit content is scoped to. Has ≥1 parent and ≥1 child. Owns the
  account boundary (today's `family_owner` role generalizes to "a member of the family").
- **Parent** — a member of exactly one family (v1). Multiple parents per family.
- **Child** — belongs to exactly one family; a data subject in their own right (the
  parent consents *on their behalf*). Stories and programs hang off a child.
- **Therapist** — an independent principal *assigned* to a child/program (not a family
  member). May be assigned across families; sees only what they are assigned.
- **Program** (Decision 5) and the existing **Story / Goal / SessionFeedback** hang off a
  **child**, not a story, so progress and content aggregate at the child level.

Relationships are the authorization graph: *content for a child is visible to that
child's family members and the therapist(s) assigned to that child/program — no one
else.* This generalizes ADR-004's per-story grants to **child-scoped** grants that
stories/programs inherit.

**Decision 3 — Real accounts replace the single local principal behind the ADR-004
`IdentityProvider` seam; authorization stays deny-by-default and moves from per-story to
child-scoped.** ADR-004 already made identity a provider-agnostic seam with a real,
complete authorization model; this ADR fills the seam with a family/child/therapist
identity source and lifts the grant unit from `story_id` to `child_id` (a story/program
authorizes via its child's grants). The `GuardedStore` boundary, audit log, fail-closed
semantics, and role→action model are **kept**; only the *identity source* and the *grant
scope* change. Authentication (how a person proves who they are) remains a
deployment concern, still behind the seam.

**Decision 4 — Capture the *child's* DOB only; do not capture parent/therapist DOB.**
The stated purpose of DOB (b.5) is **age-aware progress patterns** — that is a property of
the *child*, not the adults. So data minimization (Art. 5(1)(c)) says: the child's DOB is
arguably necessary for that purpose and may be captured *if* Decision 7 clears it;
**parent and therapist DOB are not necessary and are not collected.** Open sub-question
for the DPIA (Decision 7): whether even the child needs *full DOB* or a coarser **age
band / birth month-year** suffices for progress norming — prefer the least-granular form
that serves the purpose.

**Decision 5 — A `Program` is therapist-owned, child-scoped, and reuses the M1 progress
substrate; a parent-facing report is a derived, non-clinical view.** A program is the
therapist's plan for a child: a set of **goals** (already modeled), the **content**
(stories/premises) that serve them, and the **tracking** (the existing feedback → measure
→ suggest primitives, still gated on the ADR-002 D7 policy). Establishing a program is a
therapist action; **reporting to parents** is a *read model* over the tracking, framed as
a non-clinical engagement/independence indicator (CONTENT_SAFETY §3/§7 — never a clinical
score or diagnosis). Program content and tracking inherit the child's access scope
(Decision 3): family + assigned therapist only.

**Decision 6 — The story-authoring template is a structured input that lowers to a scene
script, and is independent of the identity work.** Today a parent provides free text; the
template makes authoring guided and complete (beginning→end structure, prompts for the
details the pipeline needs) while producing the **same scene-script contract** the
renderer already consumes. It collects **the same data as today** (story + child first
name), so it is **not** gated by Decision 7 and can proceed first.

**Decision 7 — Accounts and DOB are a processing expansion and are gated on a DPIA
revision; no identity/DOB/account code ships until it clears.** Because (b)/(c) add
personal data and a data model the current DPIA/PRIVACY explicitly exclude, the following
must land **before** identity/DOB/account code:

7.1 **DPIA revised** — new data categories (child DOB, account/contact identifiers,
program/progress records), the R-register updated, and the necessity/proportionality of
DOB (Decision 4) justified (or downgraded to an age band). **Drafted:**
`docs/DPIA_ADDENDUM_accounts_and_dob.md` (Draft v0.1) assesses this expansion and lists the
decisions it needs from the DPO — awaiting that review.
7.2 **Lawful basis re-examined** — accounts and the therapist⇄family relationship change
who the controller/processor are; the parent-on-behalf-of-child consent, and any
therapist-organization data-sharing, need a basis (the DPO package's open "accounts,"
"controller/processor," and "retention justification" gaps already anticipate this).
7.3 **Parent notice + consent updated and re-versioned** (KC-8 mechanism already ties
consent to a notice version), covering DOB, accounts, and program/progress sharing.
7.4 **Retention + erasure extended to accounts and DOB** — hard-delete (KC-1) and
crypto-shred (KC-10) today sweep a story dir; an account/family/child/program model needs
its own deletion story and a test.
7.5 **DPO/counsel note** that the expanded model is acceptable for the intended launch.

The story template (Decision 6) and continued single-operator use are **exempt** — they
add no new data. This ADR flips Proposed→Accepted for the *domain shape* once the owner
ratifies it; **building (b)/(c) is a separate, later event** gated on 7.1–7.5, exactly as
enabling the M1 engine is gated on ADR-002 D7.

## Consequences

### Positive
- The costly seams already exist: `IdentityProvider` (ADR-004 D3), child-adjacent role
  model, progress primitives, scene-script contract. This ADR mostly *composes* them.
- Sequencing by data risk lets real product value (the story template) ship now without
  waiting on the privacy/legal work.
- Data minimization is strengthened, not weakened, where we can: parent/therapist DOB is
  dropped, and child DOB is pushed toward the least-granular form that serves the purpose.

### Negative
- A family/child/program identity model is a substantial new domain — more surface, more
  to secure, and more to delete correctly (7.4).
- We introduce personal data (DOB, accounts) that the product has so far deliberately
  avoided; the privacy/DPIA cost is real and front-loaded (Decision 7).
- Child-scoped grants are a migration from per-story grants (ADR-004) — existing stores
  and tests assume the flat model.

### Neutral
- Authentication is still deferred behind the seam; this ADR decides the *authorization
  graph*, not the login mechanism.
- The program report is a read model; it adds no authority (a therapist still decides,
  ADR-002/003), only visibility.

## Alternatives considered
- **Capture DOB for all personas (as literally stated in b.4).** Rejected for the adults
  on minimization grounds — their age does not serve the progress-pattern purpose; only
  the child's does (Decision 4).
- **Keep flat per-story access, tag stories with a family id.** Rejected: progress and
  content genuinely aggregate at the child level (multiple stories per child), so the
  grant unit should be the child, not the story.
- **Build identity first (feature order).** Rejected: it front-loads the gated,
  privacy-expanding work and blocks the low-risk story template behind it (Decision 1).
- **Full birth date vs. age band for the child.** Left open for the DPIA (Decision 4/7.1)
  — recorded as a real minimization choice, not silently taking the more granular option.

## Open questions (for the DPIA / DPO, Decision 7)
- Does age-norming need full DOB, or does a birth month-year / age band suffice?
- Controller/processor split when a therapist belongs to an external clinic/organization;
  is a DPA needed between WeGoFwd2020 and the therapist's org?
- Consent model when the **child** is the data subject but the **parent** consents — and
  how a therapist's access is authorized (family grants it? the platform? a referral?).
- Can a therapist be assigned across multiple families, and what isolates one family's
  data from another in that case?
- What exactly may a parent-facing progress **report** contain to stay non-clinical
  (CONTENT_SAFETY §3/§7)?

## Migration / rollout
1. **Now (ungated):** build Decision 6 — the story-authoring template → scene script.
2. **Ratify** this ADR's domain shape (Proposed→Accepted) with the owner.
3. **Gate 7.1–7.5** — DPIA revision + notice/consent update + retention/erasure design +
   DPO note. No identity/DOB/account code before this.
4. **Then:** implement Decision 3 (accounts behind the `IdentityProvider` seam, grants
   lifted to `child_id`) → Decision 5 (Program + parent report) on top.

*This ADR records a direction and a gate; it authorizes no processing of new personal
data on its own.*
