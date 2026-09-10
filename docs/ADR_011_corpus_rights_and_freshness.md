# ADR-011 — Corpus rights, provenance and freshness: what may be ingested, and how it stays true

**Date:** 2026-09-10
**Status:** Proposed
**Branch at decision:** main

---

## Context

ADR-010 makes the corpus the whole product: every claim the assistant makes, and every
grounded story the generator writes, rests on what is in it. Two questions therefore
determine whether the asset is worth anything — **may we lawfully hold this?** and **is it
still true?**

Both are easy to get wrong in this specific domain, and a survey of the field found the
same two traps repeatedly:

**"Free to read" is not "licensed for reuse."** ERIC, PubMed, NICE and Cochrane are all
freely readable and none of them broadly permits commercial redistribution. Cochrane's
publisher goes further and expressly reserves rights for text and data mining and for
training artificial intelligence.

**"Federally funded" is not "federally authored."** 17 U.S.C. §105 places works of US
government *employees* in the public domain. It does not reach grantees or contractors:
under 2 CFR 200.315(b) a grantee retains copyright and the agency merely reserves a
royalty-free licence *for federal purposes*. That licence runs to the government, not to us.
This one rule decides most of the hard cases below — and it is why the single most valuable
practice layer in the field is the one we may not take.

There is also a trap specific to *this* domain rather than to licensing generally: in
special-needs practice, **withdrawn guidance and retired clinical reports are more dangerous
than merely stale content**, because they read as authoritative while being wrong. A
retracted study surfaced without its retraction is the worst output this system can produce.
Freshness here is not a crawl schedule; it is a supersession problem.

## Decision

**Decision 1 — Three tiers plus a prohibition list, and nothing is ingested without a tier
assignment.**

**Tier 1 — ingest now (commercially clean).**

| Source | Basis |
|---|---|
| CDC, incl. *Learn the Signs. Act Early.* | CDC states most of its site content is not subject to copyright, is in the public domain, and may be freely used or reproduced |
| US Dept of Education — IDEA, OSEP/OSERS guidance, policy letters | ED states its website information is in the public domain and may be reproduced without permission unless stated otherwise |
| NIH / NICHD / IACC | §105 federal-employee works — *per-document check; no explicit site notice was located* |
| CMS / Medicaid federal material, incl. 1915(c) waiver applications filed with CMS | Federal submissions, substantively regulatory — *notice page unverified; confirm* |
| **CPIR / parentcenterhub.org** | States "This product is public domain. Authorization to reproduce it in whole or in part is granted," with a requested citation form and the OSEP non-endorsement disclaimer. **Best-in-class plain-language source** |
| State statutes and administrative regulations (DD, Medicaid, education) | Government edicts doctrine — *Georgia v. Public.Resource.Org* (2020): statutes, regulations and official administrative rulings cannot be copyrighted at any level of government |
| **PMC Open Access Subset, filtered to CC0 and CC BY** | PMC explicitly partitions the OA subset by commercial-use permission; retrieval must go through the permitted APIs (PMC Cloud, OAI-PMH, E-Utilities, BioC) |

**Tier 2 — licence first, do not ingest by default.** AFIRM and NPDC/NCAEP (Decision 5);
AAP clinical reports; NICE (UK-territory only, so out of scope under ADR-009 D4 regardless).

**Tier 3 — cite and link, never ingest.** ERIC full text (publishers license display *to
ERIC*; submitters license IES, and all submitters retain copyright — the licence does not
run downstream); Cochrane; Campbell Systematic Reviews (article-level licence verified as
CC BY-**NC**, despite common description as CC BY); WHO non-classification content (CC
BY-NC-SA 3.0 IGO — permission required for commercial use); paywalled journals; PMC
"free-to-read" non-OA material and PubMed abstracts.

**Never.** Commercial assessment instruments and anything from them — items, scoring tables,
cut-offs, protocol text (ADOS-2, ADI-R, SRS-2, CARS-2, Vineland-3, BASC, GARS, SIS,
M-CHAT-R/F). Published curricula and textbooks. Social Stories™ materials (ADR-007 D8).
Scraped user-generated content (Decision 7).

**A caution on two Creative Commons terms.** CC BY-**ND** material (WHO classifications such
as ICF and ICD-11) permits commercial use but forbids derivatives — verbatim retrieval and
quotation is fine, while generated paraphrase is arguably an adaptation. CC BY-**SA** raises
a copyleft question for generated output. The safe core of the literature tier is therefore
**CC0 and CC BY only**; ND and SA need legal review before inclusion.

**Decision 2 — Every chunk carries a rights record, and ingestion refuses a source without
one.**
Mirroring ADR-008's provenance discipline. Per source: canonical URL, publisher, licence
identifier, the **verbatim terms text or a dated quotation of it**, tier, attribution string,
required disclaimers, retrieval date, verifier and verification date, and any
derivative/commercial restriction. A source whose terms could not be determined is recorded
as **unclear — needs legal review** and is *excluded*, not admitted on optimism. "No licence
stated" is not permission.

**Decision 3 — Attribution and disclaimers are rendered with the answer, automatically, from
the rights record.**
Not a credits page. Where CC BY requires attribution, the attribution appears with the claim
it supports. Where a federal source requires a non-endorsement disclaimer, that disclaimer is
carried — for a commercial product it is a condition of use, not decoration. Federal agency
logos and marks are never used. ADR-010 D2 already requires a citation on every claim, so the
licence obligation and the safety architecture are discharged by the same mechanism; this
decision only fixes that the *rendered* form is derived from the record rather than
hand-written.

**Decision 4 — Freshness is per-source cadence plus first-class supersession.**

| Layer | Cadence |
|---|---|
| State Medicaid HCBS waivers (amendments file continuously between renewals) | Monthly, per-state diff |
| State DD agency guidance, provider manuals, rate schedules | Quarterly, plus a pass after each legislative session |
| Federal sub-regulatory guidance (OSEP Dear Colleague letters, CMS bulletins, ACL notices) | Monthly — **withdrawal detection is a first-class requirement**; guidance is rescinded as well as issued |
| IDEA statute and 34 CFR Part 300 | Annually |
| AAP clinical reports | Semi-annually, specifically to catch **retirements** under the reaffirm-or-retire cycle |
| CDC content (milestone checklists were substantively revised in 2022; ADDM on a ~2-year cycle) | Semi-annually, and on ADDM release |
| CPIR / parent-centre material | Quarterly |
| PMC OA literature | Incremental weekly/monthly — **retraction handling is mandatory** |
| NCAEP/AFIRM EBP list (~6-year review cycle) | Annually |

Every chunk carries a status: `current`, `superseded_by(<id>)`, `withdrawn`, `retracted`. A
non-`current` chunk is either suppressed from retrieval or served with its status stated —
never silently. This is the mechanism ADR-010 D5 depends on.

**Decision 5 — AFIRM/NPDC: the highest-value layer has no licence at all. Do not ingest;
choose one of two lawful routes.**
The AFIRM modules are the operational how-to layer for the evidence-based practices, and
they are exactly what personas P2 and P3 want. The site carries no terms of use, no
copyright notice and no permissions statement. Combined with 2 CFR 200.315(b), the correct
reading is that UNC holds copyright and **absence of a licence is not permission**.

Two routes, and they are not exclusive:

1. **Ask.** Write to FPG for a written licence. This is a plausible request from a
   mission-aligned product and it is the single highest-value rights conversation available.
2. **Build around it.** The *findings* — which practices have an evidence base, and their
   names — are facts and are not themselves copyrightable; the modules' *expression* is. So
   cite AFIRM as a pointer, and author original procedural text against the underlying
   primary studies in the Tier-1 literature.

Route 2 is the default, because it is available immediately and unblocked. Route 1 is worth
starting in parallel and losing nothing if it fails.

**Decision 6 — Michigan first for the state layer; each further state gets its own rights
check.**
Statutes and regulations are free everywhere under the edicts doctrine. **Agency guidance,
provider manuals and transition handbooks are not**, and state posture varies sharply —
Florida and New Jersey treat public records as freely reproducible including commercially;
Arizona, Pennsylvania and New York assert copyright in state works. Per ADR-009 D4, Michigan
is the depth state; every state added afterwards carries a rights review as part of onboarding
it, not as a later cleanup. State transition handbooks are frequently university- or
contractor-authored and fall back into the grantee-copyright trap.

**Decision 7 — No scraped user-generated content, on two independent grounds.**
Forums, parent groups, social media, blogs. Each post is individually copyrighted and
platform terms forbid scraping — but the decisive objection is that it is health information
about identifiable people, frequently minors, who never consented. A project whose entire
privacy posture is built on minimising one consenting family's data cannot build its corpus
out of thousands of non-consenting ones. This is not a close call and it is not revisitable.

## Consequences

### Positive

- A corpus that can be defended line by line: every chunk names its source, its licence and
  its verification. "What is this built on?" has a complete answer, which is unusual in this
  category and is itself a differentiator.
- Tier 1 alone is substantial and free: federal policy, IDEA, CDC, CPIR's plain-language
  layer, state law, and a filtered slice of the peer-reviewed literature. Work can start
  immediately with no licence negotiation and no spend.
- Supersession and retraction handling turns the domain's sharpest failure mode — confidently
  serving withdrawn guidance — into a tracked, testable property.
- Rights records make later expansion cheap: adding a state or a source is a form to fill,
  and the refusal-without-a-record rule prevents quiet accumulation of unlicensed material.
- Route 2 in Decision 5 means the AFIRM gap does not block anything.

### Negative

- The first corpus will be stronger on **policy, rights and research** than on **step-by-step
  practice**, because the practice layer is the encumbered one. That is a real product gap
  and users will feel it.
- Excluding ERIC full text removes the richest special-education practice literature
  available. Citing and linking is a poor substitute for retrieval over it.
- Per-state rights review does not scale by effort alone; a fifty-state product needs either
  counsel throughput or a much narrower state layer.
- Monthly waiver diffs and retraction watching are ongoing operational cost with no
  end date — a maintenance commitment taken on permanently, not a project.
- Verbatim-terms capture and verification dates are tedious, and the discipline will feel
  disproportionate right up until the moment it is not.

### Neutral

- Chunking, embedding and index choices are independent of rights and belong to ADR-010.
- Tier assignments are expected to move as terms are clarified or licences obtained; the
  register is versioned so a change is visible.

## Alternatives considered

- **Ingest everything reachable and handle complaints later.** Rejected. Beyond the legal
  exposure, it is incompatible with a product asking families to trust it with a child's
  story, and it forfeits the defensibility that is most of the asset's value.
- **Rely on fair use for research literature.** Rejected as a foundation. It is a defence,
  not a permission; it is fact-specific and untested for commercial retrieval corpora; and
  Cochrane's publisher has expressly reserved AI-training rights, which is precisely the
  posture that makes a fair-use argument hard.
- **Treat "no licence stated" as permissive.** Rejected — Decision 5. It is the exact
  inversion of copyright's default and it is the most common way a corpus becomes
  unlicensable in retrospect.
- **Assume all federally funded work is public domain.** Rejected — 2 CFR 200.315(b). This
  is the single most consequential misconception in this domain.
- **Skip supersession; show dates and let readers judge.** Rejected for withdrawn, rescinded
  and retracted material. A date does not tell a volunteer that guidance was rescinded.
- **Scrape parent forums for lived-experience content.** Rejected — Decision 7, on privacy
  grounds independent of copyright.
- **Start with NICE because the guidance is the best written.** Rejected: its open content
  licence is offered for the United Kingdom only, and outside the UK its content may not be
  reused without prior written agreement. Excluded under ADR-009 D4.

## Migration / rollout

- **Not yet started.** Proposed. Decision 1's tiering should be reviewed by counsel before
  Tier-1 ingestion begins in volume — a short, bounded engagement, and the highest-value
  legal spend in the whole programme.
- **Ratification condition (Proposed → Accepted):** the rights register implemented, counsel
  review of the tier list complete, and the Tier-1 spine ingested with a rights record on
  every source and no source admitted without one.
- **Tickets:** `KC-18` (corpus package + Tier-1 spine), `KC-19` (rights records + attribution
  rendering), `KC-20` (freshness, supersession, tombstones, retraction watch).
- **Verification debt to close first** — items the survey could not establish and which must
  be settled rather than assumed: AFIRM/NPDC terms (none published); an explicit NIH/IACC
  copyright notice; the CMS website-policies notice; AAP permissions terms; ERIC's own
  copyright page; and per-site terms for individual state PTIs and UCEDDs.
- **Docs:** `docs/CORPUS_RIGHTS.md` (the living register, versioned in-repo so a tier change
  is reviewable in a diff); `docs/KNOWLEDGE_BASE_PLAN.md`; `docs/DPIA.md` (record that the
  corpus contains no personal data — Decision 7 and ADR-009 D6 — rather than leaving it to
  inference).
- **Tests (fixtures only):** ingestion refuses a source with no rights record; a Tier-3
  source cannot be ingested even if reachable; a retracted or withdrawn chunk is never
  returned as current; the rendered attribution and disclaimer for a chunk match its rights
  record exactly; an ND-licensed chunk is served verbatim and never paraphrased.
