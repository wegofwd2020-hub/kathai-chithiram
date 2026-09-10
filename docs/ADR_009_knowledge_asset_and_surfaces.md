# ADR-009 — One knowledge asset, two surfaces: widening from a story generator to a practice knowledge base

**Date:** 2026-09-10
**Status:** Proposed
**Branch at decision:** main

---

## Context

Kathai Chithiram is built around one act: a parent describes their child's situation and
receives an animation. Every artefact in the repository serves that act — the scene-script
contract, the render guards, the review gate, per-story encryption, `NameMapping`, KC-1
hard-delete. The system knows exactly one user (a parent, mediated by an operator) and
produces exactly one thing (a video for a child).

Three further audiences have been identified, and they are not variations on that user:

- **(A) People learning to assist people with special needs** — therapists in training,
  direct-support professionals, classroom aides, volunteers, extended family.
- **(B) People whose needs change across a lifespan** — the same person at 6, at 12, at 19
  and at 30 needs different supports, and the adults around them must keep re-educating
  themselves as school-based entitlements end and adult services begin.
- **(C) Practitioners, programme designers and assistive-device developers** — people
  building services and products for this population.

None of these people want an animation. They want an **answer**. That is a different
product, and the temptation is to treat it as "the same LLM, pointed at a chat box."

It is not the same system:

| | Story generator (built) | Practice assistant (proposed) |
|---|---|---|
| Output | A structured artefact — scene script → rendered video | Free text read by an adult |
| Consumer | A child, via a reviewed artefact | An adult decision-maker, directly |
| Failure mode | A wrong picture or wrong pacing, caught at review | Wrong information, acted on immediately |
| Safety architecture | Contract validation + render guards + human review gate | Citation grounding + refusal + scope limits |
| Right ML technique | Constrained decoding + a tuned adapter (ADR-006) | Retrieval — and explicitly **not** facts in weights (ADR-010) |
| Freshness | Irrelevant; a story about handwashing does not expire | **Dominant**; a state's waiver rules change monthly |
| Personal data | Special-category data about a named child | None, by design (Decision 6) |

Reading that table, the framing "the goal of Kathai Chithiram is too small" is not quite
right. The goal is the right size; what has been discovered is that **the product is a
surface on a larger asset that does not yet exist.** The asset is a curated, citable,
versioned, rights-cleared body of special-needs practice knowledge. The story generator
consumes it to write better stories. The new audiences consume it to get answers. Building
a second chat product without first building that asset would produce a plausible-sounding
autocomplete over a domain where being plausible and wrong is the specific harm.

This ADR fixes the scope, the personas, the boundary and the sequence. ADR-010 fixes the
architecture; ADR-011 fixes the rights and freshness regime.

## Decision

**Decision 1 — Adopt an asset-and-surfaces model. The corpus is a shared package with its
own canonical home.**
The knowledge base becomes a shared in-process package in the `wegofwd` family, alongside
`wegofwd-llm` and `wegofwd-video` and following the pattern in `docs/shared-services.md` —
proposed name **`wegofwd-arivu`** (அறிவு, *knowledge*), keeping the Tamil naming of the
product family; the name is the owner's call. Two consumers:

- **Kathai Chithiram** retrieves from it to *ground generation* — a story about a first
  dental visit informed by published desensitisation practice rather than a model's priors.
- **The practice assistant** retrieves from it to *serve answers* to audiences A–C.

The corpus is the asset. The surfaces are replaceable; the corpus is not.

**Decision 2 — Name four personas, and serve them in a stated order.**

| # | Persona | Wants | Verdict |
|---|---|---|---|
| P1 | **Parent / guardian** | A story for their child | **Served today.** Unchanged by this ADR |
| P2 | **Helper-learner** (aide, DSP, volunteer, trainee, family member) | To understand how to support this person well | **First new surface.** Highest value, lowest risk, best corpus fit |
| P3 | **Lifespan navigator** (parent or professional at a transition point) | To know what changes at 3, at 14, at 18, at 22, and what to do about it | **Second.** Highest real-world need, hardest corpus, highest hazard |
| P4 | **Builder** (practitioner, programme designer, device developer) | Literature, standards, implementation evidence | **Not a product. A by-product** |

On **P4**: it bundles three audiences whose questions barely overlap — a clinician wants the
intervention literature, a programme designer wants implementation science and funding
mechanics, a device developer wants human-factors and regulatory pathways. Scoping that as a
product means "be a search engine for a field," which is unbounded and undifferentiated.
P4 is what P2 and P3 *become* once the corpus is deep: the same corpus answered in a
professional register. Serve it when it falls out; do not plan it.

On **P3**: the observation that needs change across a lifespan is the strongest insight in
this expansion, and it applies to the *story* product too — the same child needs different
stories at 6 and at 19, on a different axis from the within-goal progress `ProgressPolicy`
measures. That link is worth pursuing later; it is out of scope here.

**Decision 3 — The product law: educate, always cite, never advise.**
This is the boundary that keeps the system out of clinical decision support, and it is a
hard constraint, not a tone preference. The assistant:

- **explains** what a practice is, what the evidence says, how a process works, what a term
  means, what typically changes at a life stage, and **who to ask next**;
- **never** issues an individualised recommendation about a specific person, **never**
  determines or predicts eligibility for a service or benefit, and **never** performs or
  interprets assessment, screening or diagnosis;
- **cites, or refuses.** An answer with no retrieved supporting source is not produced.

The reasoning is regulatory as well as ethical. FDA's revised clinical-decision-support
guidance turns on a transparency criterion: whether a health-care professional can
independently evaluate *the basis* for a recommendation rather than relying primarily on
the software, with recommendations grounded in well-understood and accepted sources rather
than a proprietary algorithm. A citation-grounded system that shows its sources satisfies
that criterion by construction. A system that answers from model weights cannot — there is
no basis to review. Staying on the education side of the line, and citing every claim,
keeps the product outside device regulation on the merits rather than on a disclaimer.

It also aligns with obligations already in this repository: `CONTENT_SAFETY.md` §3's "no
medical claims, diagnoses, or therapeutic promises" and ADR-001 D5's "automation is never
the sole safeguard."

**Decision 4 — Jurisdiction: United States; Michigan first for depth, federal for breadth.**
Federal material (CDC, ED/IDEA/OSEP, NIH/NICHD, CMS) is public domain and clean, and gives
national breadth immediately. State-level material is where P3's real questions live —
waivers, waitlists, transition, adult services — so depth starts with **one** state, and
Michigan is the one the project is in. Additional states are added on demand, each with its
own rights check (ADR-011 D6), because state copyright posture varies and state guidance
changes monthly.

Two exclusions follow: **NICE guidance is out** (its open-content licence is offered for
the United Kingdom only; outside the UK its content may not be reused without prior written
agreement), and **no EU users at launch**, which defers EU AI Act Annex III high-risk
obligations for education and for eligibility-for-benefits systems. Both are revisitable
decisions, and both should be revisited deliberately rather than by accident of a signup.

**Decision 5 — Build the corpus now; ship the assistant surface after Kathai Chithiram
ships.**
The corpus is librarian and pipeline work: ungated, needing no clinical collaborator, no
GPU, no training run, and no new personal-data processing. It is the one part of this
expansion that can start immediately, and it **improves the existing product** through
retrieval grounding while it is being built. The assistant surface waits.

This is a scope-discipline decision as much as an architectural one. The project is a solo
build, under a ~$25k envelope, with two tracks (M1, and now the ADR-006 domain-model
programme) already blocked on a clinical collaborator who is not yet retained. Opening a
second consumer product in parallel is the most reliable way to ship neither.

**Decision 6 — The assistant holds no personal data, and must not accept a description of
a specific real person.**
Kathai Chithiram processes special-category data about a named child and carries a large
apparatus for it — consent gates, pseudonymisation, per-story envelope encryption,
verifiable hard-delete, deny-by-default access control. **The assistant must not inherit
that apparatus, and must not need it.** A question like "what does the research say about
visual schedules for transitions?" contains no personal data at all.

Conflating the two would be an error in both directions: it would burden a
no-personal-data service with machinery it does not need, and it would quietly extend a
regime designed for one child's story to a free-text box where a volunteer might type a
health disclosure about a person who never consented.

So the input is guarded: a question that describes a specific real individual is
**declined and redirected**, not answered and not stored. This is simultaneously a privacy
control, a scope control (Decision 3 forbids individualised answers anyway), and — usefully
— a single enforcement point for all three.

**Decision 7 — The scope boundary requires an escalation path, and that path is the
unbuilt `CONTENT_SAFETY.md` §4 item.**
A volunteer will ask "what do I do when he hits himself." That is not a corpus question and
it is not an out-of-scope question either; it is a person in front of a situation, needing a
human. `CONTENT_SAFETY.md` §8 has carried "define the risk-of-harm handling path with
appropriate resources" as an open item since ADR-001, and it is the project's largest
unbuilt safety gap.

**Serving persona P2 makes that path a precondition rather than a discovery.** Treat it as
one: no assistant surface ships until the escalation route exists, is authored with the
professional collaborator, and routes to a person and to real resources. Per ADR-001 D5 the
model detects and routes; it never triages and never decides.

## Consequences

### Positive

- Reframing from "a story product" to "a knowledge asset with surfaces" makes the expansion
  coherent instead of scattered, and gives one thing to invest in rather than three.
- The corpus improves the existing product before any new surface exists — grounded
  generation is a real quality gain for stories, so the work is not speculative.
- P2 is genuinely underserved: direct-support professionals and volunteers turn over
  constantly and receive little durable training, and nothing in the corpus for them
  involves personal data or clinical judgement.
- The educate-cite-never-advise law makes the regulatory posture a design property rather
  than a disclaimer, and it happens to be the same architecture that makes the answers
  trustworthy and that satisfies the corpus's own attribution obligations (ADR-011 D3).
- Deferring P4 avoids the unbounded commitment while still serving it later for free.
- Decision 6 keeps a large privacy surface from opening at all, which is far cheaper than
  managing one.

### Negative

- A second product, even deferred, is a second thing to maintain, fund and keep in scope. A
  solo builder's real risk here is dilution, and Decision 5 mitigates but does not remove it.
- The educate-never-advise line will frustrate users. The most valuable question a parent
  asks — "does my child qualify for this?" — is exactly the one the system refuses. Refusing
  it well, with the right pointer to a human, is a product design problem, not a copy problem.
- Michigan-first depth means the assistant is markedly better for one state than for the
  other forty-nine, which is awkward to communicate.
- The corpus's highest-value practice layer is rights-encumbered (ADR-011 D5), so the first
  version will be stronger on policy and research than on step-by-step how-to.
- Making the risk-of-harm path a precondition is correct and will delay the surface.

### Neutral

- The package name is a branding choice; the architecture does not depend on it.
- Whether the assistant eventually lives in this repository or its own is deferred. The
  corpus package's boundary is what matters, and it is fixed here.

## Alternatives considered

- **Bolt a chat surface onto Kathai Chithiram now.** Rejected: it would produce fluent,
  uncited, unversioned answers over a domain where fluent-and-wrong is the harm, and it
  would inherit a child-data regime it does not need while lacking every safeguard it does.
- **Treat the assistant as an entirely separate venture, no shared asset.** Rejected: the
  corpus is precisely what both need, and duplicating it doubles the only expensive part.
- **Serve all four personas from day one.** Rejected: P4 bundles three unrelated audiences
  and is unbounded; and a solo builder serving four personas serves none.
- **Pause the story product and pivot to the knowledge system.** Considered and not chosen:
  the generation pipeline is essentially complete and blocked only on external sign-offs, so
  abandoning it now would forfeit finished work for an unbuilt bet.
- **Allow case-specific suggestions for verified professionals.** Rejected for now: it puts
  the product inside clinical decision support, requires the independent-review criterion
  designed in from the start plus identity verification and role attestation, and needs
  counsel. Revisit as a deliberate, resourced decision — never as a feature flag.
- **Include eligibility navigation ("what might they qualify for").** Rejected as stated:
  eligibility determination is both the highest-harm error (a missed waitlist enrolment can
  cost years) and squarely within the EU AI Act's high-risk category for access to essential
  services. The lawful and useful version is *navigational* — here is what your state's
  documentation says, here is the source, here is who decides — which Decision 3 permits.

## Migration / rollout

- **Not yet started.** Proposed; nothing has landed.
- **Ratification condition (Proposed → Accepted):** ADR-011's rights tiering reviewed by
  counsel, and the Tier-1 corpus spine ingested with rights records attached — i.e. the
  asset demonstrably exists before its scope is ratified.
- **Order:** corpus spine → rights and freshness regime → grounding into the existing
  generator → (Kathai Chithiram ships) → risk-of-harm path → assistant surface for P2 →
  Michigan depth for P3.
- **Tickets:** `KC-18` (corpus package + Tier-1 spine), `KC-19` (rights records + attribution
  rendering), `KC-20` (freshness, supersession and tombstones), `KC-21` (retrieval grounding
  for story generation). The assistant surface has no ticket yet and should not get one
  until the risk-of-harm path does.
- **Docs:** `docs/KNOWLEDGE_BASE_PLAN.md` (phases, costs, gates); `docs/shared-services.md`
  (add the new package to the family); `docs/BACKLOG.md` (M4 milestone). `docs/DPIA.md`
  needs **no** new risk for the corpus itself — Decision 6 means no personal data — but
  should record that fact explicitly rather than by silence.
- **Explicitly out of scope for this ADR:** the retrieval architecture (ADR-010), the rights
  and freshness regime (ADR-011), and the risk-of-harm handling path, which remains a
  safeguarding design owned with a professional and must not be absorbed into a
  knowledge-base programme.
