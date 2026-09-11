# ADR-013 — The practice-assistant surface and its commercial model

**Date:** 2026-09-11
**Status:** Proposed
**Branch at decision:** main

---

## Context

ADR-009 established the product as one knowledge asset — the **context dictionary** — with
replaceable surfaces on top of it. Two surfaces are named there:

- **Surface 1 — Kathai Chithiram** (the animation). Built and shipping; a child-facing
  artefact produced from special-category child data.
- **Surface 2 — the practice assistant** (ADR-009 personas P2 helper-learner, P3 lifespan
  navigator): a **direct-query skin** where an adult asks a question and receives a cited
  answer. ADR-009 names it; its interface is not yet designed ("to be defined").

Two owner intentions now need a decision of their own, because both touch the product's
hard boundary rather than just its feature set:

1. **The corpus is informed by professional clinicians and therapists.** This is a statement
   about *where the knowledge comes from* (authoring and adjudication — ADR-008, ADR-011, the
   collaborator ADR-002/ADR-006 already require), **not** a statement that the surface gives
   live clinical advice. The distinction is load-bearing and is easy to blur.

2. **The commercial model is product promotion.** Alongside the cited educational answer, the
   assistant would surface **products available for sale** relevant to the scenario — for
   *"what capabilities does a house need for a senior with a hearing disability?"*, the visual
   smoke alarms, bed-shaker alarms and doorbell signallers that address it — as affiliate,
   marketplace or sponsored listings. The owner's reference point is "the kind of promotion
   Google, Amazon and other engines do."

Product promotion is, on its face, a form of recommendation, and **ADR-009 Decision 3 — the
product law: educate, always cite, never advise** — is precisely the line that keeps this
product (a) outside medical-device / clinical-decision-support regulation and (b) trustworthy
to a vulnerable audience. Bolting a paid layer onto a citation-grounded reference for seniors
and disabled people, done carelessly, forfeits both at once. This ADR does not decide whether
to monetise — several sub-decisions remain the owner's (see *Open questions*) — it fixes the
**boundaries** any commercial layer must obey so the answer to "should we?" is not
foreclosed by an architecture that already leaked.

## Decision

**Decision 1 — The commercial layer lives only on the practice-assistant surface, and never
touches the child product or any child-data context.**
Kathai Chithiram processes special-category data about a named child and carries consent,
pseudonymisation and hard-delete machinery for it (ADR-001, KC-1). No promotion, affiliate
link, sponsored listing or product placement appears in the animation product, in the parent
authoring flow, or anywhere a child's story or identity is in scope. Commerce is a
Surface-2-only concern. ADR-009 Decision 6 (the assistant holds no personal data) is
unchanged: a marketplace layer keyed to a *scenario category* needs no personal data either.

**Decision 2 — Two separated layers, and money never bends the educational answer.**
The assistant renders two visibly distinct things:

- **Layer A — the cited educational answer.** Grounded in the corpus, every claim attributed
  (ADR-009 D3; ADR-011 D3). **Its content, ordering and inclusion are never influenced by any
  commercial relationship.**
- **Layer B — a clearly-labelled "products that address this" section**, below Layer A and
  visibly separate, carrying disclosed commercial listings.

The hard rule — the commercial analogue of ADR-009 D3 — is that **money never bends Layer A.**
The moment a paid relationship changes what the educational answer says, what it cites, or the
order it presents options in, both the regulatory posture and the trust that justify the
product are gone. This separation is the same church-and-state line a search engine draws
between results and ads, applied to a higher-stakes domain.

**Decision 3 — Categories and options, disclosed — not individualised purchase advice.**
Layer B presents **product categories that address the scenario** ("visual smoke alarms",
"bed-shaker alarms"), grounded in what Layer A already established, with listings **disclosed**
as commercial (affiliate / sponsored / referral — FTC material-connection disclosure is
mandatory, not optional). Layer B does **not** issue an individualised "you specifically
should buy *this* product" recommendation about a specific real person — that re-crosses
ADR-009 D3 into advice, and ADR-009 D6's decline-on-personal-description guard still applies
to the query itself.

**Decision 4 — Regulated, health-claim and medical-device products are a higher risk tier,
gated pending counsel.**
Generic, corpus-grounded categories (a doorbell signaller) are the safe core. Products that
are **regulated medical devices, or that carry health/therapeutic claims**, are a different
risk tier — promoting them can pull the surface back toward device regulation and health-
advertising law. They are **excluded or gated** until counsel clears the specific category.

**Decision 5 — Commerce is a later revenue layer, not a now-build.**
Per ADR-009 Decision 5, the assistant surface ships only after Kathai Chithiram ships, and per
ADR-009 Decision 7 no assistant surface ships until the risk-of-harm escalation path exists.
The commercial layer sits on top of that surface, so it is downstream of both. Nothing here
authorises building a marketplace now; it authorises the *shape* one may take when the surface
is built.

**Decision 6 — Counsel gate before any commercial layer ships.**
Mirroring ADR-011's "counsel reviews the rights tiering before ratification", no commercial
layer ships until counsel has reviewed: FTC endorsement and disclosure obligations; the
heightened scrutiny of **advertising health- and safety-adjacent products to vulnerable
populations** (seniors, people with disabilities); and device / health-claim promotion
(Decision 4). This ADR moves to Accepted only after that review.

**Decision 7 — Clinicians inform the corpus; the surface still does not advise. Monetisation
does not change this.**
Professional input shapes *what the dictionary knows* (authoring, adjudication — ADR-008,
ADR-011). The surface serves cited education and routes to a human where a real situation
needs one (ADR-009 D3, D7). It does not become a clinician giving live advice, and the
commercial layer touches Layer B only — it never converts the educational answer into a paid
recommendation. Keeping "clinicians shape the knowledge" and "the surface advises" apart is
what keeps the product outside clinical-decision-support regulation.

## Open questions — the owner's to decide, not decided here

- **Revenue mechanism:** affiliate links vs. sponsored (labelled) listings vs. marketplace
  referral fees. Each has a different disclosure and conflict profile.
- **Timing:** is the commercial layer in the assistant's v1, or a later phase after the
  educational surface has earned trust?
- **Model choice / values:** an advertising/commerce model vs. subscription or grant funding.
  Monetising a help tool for a vulnerable population via promotion is a values call, not only
  a revenue one, and it should be made deliberately.
- **Launch categories:** which scenario/product categories are first, and which are deferred
  under Decision 4.
- **Surface-2 interface design** is out of scope for this ADR (a later design/spec).

## Consequences

### Positive

- A revenue model is defined without forfeiting the educate-cite-never-advise law that is the
  product's regulatory and trust foundation — the separation (Decision 2) is what makes the
  two compatible rather than opposed.
- Confining commerce to Surface 2 (Decision 1) keeps the child product clean and keeps
  ADR-009 D6's no-personal-data property intact for the surface that monetises.
- Stating the counsel gate (Decision 6) up front turns a latent legal exposure into a planned
  review, the same way ADR-011 handled rights.

### Negative

- A commercial layer is a standing conflict-of-interest surface. Decision 2's "money never
  bends Layer A" rule is easy to state and hard to hold; it needs enforcement (review,
  auditing of ranking) rather than good intentions.
- Advertising to a vulnerable population is reputationally and legally sensitive even done
  correctly; the mission-optics question (Open questions) does not have a purely technical
  answer.
- Deferring regulated/health-claim products (Decision 4) removes some of the highest-intent,
  highest-value inventory from the safe core.

### Neutral

- The revenue mechanism and timing are deliberately left open; the architecture here is
  compatible with any of them, which is the point.
- Whether Surface 2 and its commercial layer eventually live in this repository or move with
  the assistant to its own home is deferred (as ADR-009 already deferred the surface), and per
  ADR-012 D4 this ADR would travel with that scope if it moves.

## Alternatives considered

- **No commerce; subscription or grant funding only.** Not rejected — it is one of the open
  model choices. Recorded here so the commercial path is a deliberate decision, not a default.
- **Let paid placement influence the answer's ranking (a "blended" results model).** Rejected:
  it violates Decision 2's hard rule and collapses both the regulatory posture and the trust.
- **An open, unvetted marketplace.** Rejected for a vulnerable-population health/safety domain:
  Decision 4's tiering and Decision 6's counsel gate exist precisely because unvetted promotion
  here is the high-harm case.
- **Put commerce on the child animation too.** Rejected outright (Decision 1): special-category
  child data and product promotion must never share a surface.

## Migration / rollout

- **Not yet started.** Proposed; nothing has landed, and nothing should — the surface this
  governs is itself downstream of Kathai Chithiram shipping and the risk-of-harm path
  (Decision 5).
- **Ratification condition (Proposed → Accepted):** the counsel review in Decision 6 is
  complete, and the owner has resolved the *Open questions* (at minimum: model choice and
  timing).
- **No ticket yet**, and none should be opened until the practice-assistant surface has one,
  which ADR-009 gates on the risk-of-harm path.
- **Relationships:** extends ADR-009 (asset and surfaces) and inherits its D3/D5/D6/D7;
  parallels ADR-011's counsel-before-ratify posture; governed by ADR-012 topology.
