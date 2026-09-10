# Kathai Chithiram — Knowledge base programme plan

**As of:** 2026-09-10 · **Owner:** WeGoFwd2020 · **Shaping ADRs:** `ADR_009_knowledge_asset_and_surfaces.md`,
`ADR_010_retrieval_first_practice_assistant.md`, `ADR_011_corpus_rights_and_freshness.md`
**Companion to:** `docs/LLM_PROGRAM_PLAN.md` (the domain-model programme)

> Building the shared practice-knowledge corpus that both Kathai Chithiram and a future
> practice assistant sit on — corpus first, assistant surface after the story product ships.
>
> Scope decisions taken: **educate, always cite, never advise**; **US, Michigan first**;
> **corpus now, assistant later**.

---

## Why this is a separate plan, and why it does not compete for the same resource

`docs/LLM_PROGRAM_PLAN.md` is **clinician-paced**: its critical path is ~105 hours of a
retained collaborator's time for a rubric, a persona grid and adjudication tranches, and it
is blocked at G1 until that person exists.

This plan is **engineering-paced and cash-light**: its critical path is the owner's own
hours plus one bounded legal review, and it is blocked on nobody. The two programmes
therefore **interleave rather than compete** — corpus work is the natural thing to do while
waiting on an adjudication tranche, and phase K3 pays directly back into the story product
that the other plan is trying to improve.

That is the practical case for taking this on now despite being solo. It is not a second
front; it is the work that fits in the gaps of the first one.

---

## What is actually being built

**The asset:** a shared in-process package in the `wegofwd` family alongside `wegofwd-llm`
and `wegofwd-video` — proposed name `wegofwd-arivu` (அறிவு, *knowledge*); the name is the
owner's call. It holds rights-cleared, versioned, citable passages of special-needs practice
knowledge, each carrying a licence record and a currency status.

**Two consumers:**
- **Kathai Chithiram** retrieves from it to ground story generation.
- **A practice assistant** (later) retrieves from it to answer questions for helper-learners
  (P2) and lifespan navigators (P3).

**The product law**, in one line: *the system explains and cites; it never tells anyone what
to do about a specific person, and it never decides eligibility.* Every answer carries its
sources or it is not produced.

---

## Phases

Timings assume ~15 engineering hours/week, interleaved with the domain-model programme.

### K0 — Corpus package, rights register, Tier-1 spine *(6–8 weeks)* — `KC-18`, `KC-19`

The package skeleton, the rights-record schema, and ingestion that **refuses any source
without a rights record**. Then the Tier-1 spine: CDC (incl. *Learn the Signs. Act Early.*),
ED/IDEA/OSEP guidance, NIH/NICHD/IACC, CMS/Medicaid federal material, **CPIR /
parentcenterhub** (public domain, attribution requested — the best plain-language source
available), and Michigan statutes and administrative regulations (free under the government
edicts doctrine).

Close the verification debt in parallel: AFIRM/NPDC terms, an explicit NIH/IACC notice, the
CMS notice page, ERIC's copyright page, per-site PTI terms.

**Exit gate:** every ingested source carries a verbatim-terms rights record; a fixture source
with no record is refused by test; counsel review of the ADR-011 tier list complete.

### K1 — Literature tier *(4–6 weeks)* — `KC-18`

PMC Open Access Subset filtered to **CC0 and CC BY only**, retrieved through the permitted
APIs (PMC Cloud, OAI-PMH, E-Utilities, BioC). CC BY-SA and CC BY-ND held back pending legal
review — ND in particular is a genuine problem for a system that paraphrases.

Start the **AFIRM/FPG licence conversation** here (ADR-011 D5, route 1). It costs an email
and it is the highest-value rights conversation available. Meanwhile default to route 2:
cite AFIRM as a pointer and author original procedural text against the primary studies.

**Exit gate:** literature tier ingested with per-article licence recorded; a non-permitted
licence class cannot enter the index, asserted by test.

### K2 — Freshness, supersession, tombstones *(3–4 weeks)* — `KC-20`

Per-source re-ingestion cadence (ADR-011 D4). Chunk status `current` /
`superseded_by(<id>)` / `withdrawn` / `retracted`. Withdrawal detection for federal
sub-regulatory guidance, retirement detection for AAP reports, retraction watch for PMC.
A non-current chunk is suppressed or served with its status stated — never silently.

**Why this early:** withdrawn guidance and retired reports read as authoritative while being
wrong. This is the domain's sharpest failure mode and it should exist before anything is
served, not after.

**Exit gate:** a tombstoned source is never returned as current, asserted by test; the
cadence runs unattended.

### K3 — Ground story generation *(3–4 weeks)* — `KC-21`

The first real consumer. Retrieval informs generation — a story about a first dental visit
grounded in published desensitisation practice rather than a model's priors — behind the
**existing KC-7 human review gate**.

**Why here:** it proves retrieval end to end in the one place where a mistake is caught
before it reaches anyone, and it improves the product that is actually shipping. If
retrieval quality is poor, this is where that is discovered, cheaply.

**Exit gate:** grounded generation measurably no worse on the `kc eval` axes and better on
domain specificity; retrieved sources recorded against the generated script for audit.

---

*— Kathai Chithiram ships. Everything below waits. —*

---

### K4 — Risk-of-harm handling path *(collaborator-paced)* — **precondition, no ticket yet**

`CONTENT_SAFETY.md` §8's open item since ADR-001, and the project's largest unbuilt safety
gap. A volunteer will ask "what do I do when he hits himself." Serving persona P2 makes this
a precondition rather than a discovery.

Authored **with** the professional collaborator; routes to a person and to real resources.
Per ADR-001 D5 the model detects and routes — it never triages and never decides.

**Gate: no assistant surface ships until this exists.**

### K5 — Scope router, answer contract, evaluation *(5–7 weeks)* — `KC-22` (not yet opened)

The four scope classes; the structured answer with claims, citations, limits and a named
human next step; validation that withholds rather than repairs. The ADR-010 D7 eval axes:
groundedness, citation accuracy, refusal correctness, freshness, honest-refusal coverage.

**Exit gate:** the adversarial refusal suite passes with class-4 recall reported separately;
an uncited claim is withheld by test.

### K6 — Assistant surface for P2 *(6–8 weeks)*

Helper-learners: aides, direct-support professionals, volunteers, trainees, family.

### K7 — Michigan depth for P3 *(ongoing)*

Waivers, waitlists, transition, adult services — navigational and citational, never
determinative.

**Elapsed to K3 (the point where the existing product benefits): roughly 4–5 months**,
interleaved. K4 onward is gated on the story product shipping and on the collaborator.

---

## Cost model

The striking thing about this programme is how cheap it is next to the model programme —
because the expensive input there was clinician hours, and here there are none.

| Line | Basis | Low | High |
|---|---|---|---|
| **Counsel — ADR-011 tier review + rights register sign-off** | Bounded engagement; **the highest-value legal spend in either programme** | $3,000 | $6,000 |
| Counsel — AFIRM/FPG licence conversation, if it progresses | Only if route 1 advances | $0 | $2,000 |
| Embedding / indexing compute | ~100–300k chunks; local, or tens of dollars hosted | $0 | $150 |
| Index hosting at prototype scale | Small index, single instance | $0 | $600/yr |
| Ongoing freshness operations | ~2–4 h/month once automated; owner's time | $0 | $0 |
| Contingency | | $500 | $1,000 |
| **Total cash** | | **≈ $3,500** | **≈ $9,750** |

Everything else is the owner's engineering hours. Combined with the domain-model programme's
$17k–28k, the whole two-programme picture lands around **$21k–38k**, and the corpus half can
begin at essentially zero while the legal review is arranged.

**Not in this budget:** licence fees for Tier-2 sources (unknown until asked), per-state
rights review beyond Michigan, and any paid literature access — all deliberately deferred.

---

## Decision gates and kill criteria

| Gate | Condition to proceed | If it fails |
|---|---|---|
| **K-G0** — before volume ingestion | Counsel has reviewed the ADR-011 tier list | Ingest only the sources with unambiguous public-domain notices (CDC, ED, CPIR, state law) and wait |
| **K-G1** — after K0 | No source in the index lacks a verbatim-terms rights record | Stop and fix. A corpus that cannot name its rights is not an asset |
| **K-G2** — after K3 | Grounded generation is no worse than ungrounded on the eval axes | Retrieval quality is insufficient; fix chunking and coverage before building any answer surface on it |
| **K-G3** — before K6 | The risk-of-harm path exists, authored with the collaborator | **No assistant surface.** Non-negotiable |
| **K-G4** — before K6 | Class-4 refusal recall acceptable on the adversarial suite | No surface. Recall on harm routing is never traded against precision |

### Genuine kill criteria

- Counsel finds the Tier-1 reading materially wrong → the corpus premise needs rework before
  any further spend.
- After K1, coverage is so thin that honest refusal dominates on realistic P2 questions →
  the assistant is not viable on a lawful corpus alone; reconsider rather than paper over it
  with ungrounded generation.
- Kathai Chithiram has not shipped by the time K3 completes → **stop and finish the story
  product.** This plan exists to compound with it, not to replace it.

---

## Risks

| Risk | Likelihood | Impact | Response |
|---|---|---|---|
| The practice how-to layer stays rights-encumbered (AFIRM) | **High** | High | Route 2 by default — cite as pointer, author original text against primary studies; pursue an FPG licence in parallel and lose nothing if refused |
| Corpus too thin → constant refusal → product feels useless | Medium | High | Measure honest-refusal rate as a coverage metric from K1 onward, not at the end; K-G2 and the kill criterion above |
| Scope creep from "educate" into "advise" under user pressure | **High** | **Severe** | The line is enforced at the input by the scope router, not by prompt or copy; adversarial suite in CI |
| Freshness debt accrues silently; withdrawn guidance served as current | Medium | Severe | K2 before any surface; withdrawal and retraction detection as first-class, tested requirements |
| Per-state expansion outruns rights review | Medium | Medium | One state at a time, rights review as part of onboarding a state, never as cleanup |
| Two programmes dilute a solo builder | **High** | High | K3 is the last phase before a hard stop; the K-G kill criterion above makes "finish the story product" an explicit trigger, not a judgement call |
| A user pastes a description of a real child into the box | High | Medium | ADR-009 D6 — declined at the input, not stored; single enforcement point for scope and privacy together |

---

## What this programme must not do

- Answer a question about a specific named person, or determine eligibility (ADR-009 D3).
- Put facts into model weights (ADR-010 D1) — unciteable, unupdatable, unretractable,
  unattributable.
- Answer from general knowledge when retrieval returns nothing (ADR-010, Alternatives).
  This is the most tempting shortcut in the whole design and it converts every coverage gap
  into a confident fabrication exactly where the reader cannot tell.
- Ingest a source with no stated licence on the theory that silence is permission
  (ADR-011 D5).
- Assume federally *funded* means federally *authored* (2 CFR 200.315(b)).
- Scrape parent forums or social media — health information about identifiable people,
  often minors, who never consented (ADR-011 D7). Not revisitable.
- Inherit Kathai Chithiram's child-data machinery into a service that holds no personal data
  (ADR-009 D6).

---

## Immediate next actions

1. **Arrange the counsel review of the ADR-011 tier list.** Bounded, and it unblocks
   everything else.
2. **Email FPG about an AFIRM licence.** Costs nothing, and it is the highest-value rights
   conversation available.
3. **Start K0 with the three unambiguous sources** — CDC, ED/IDEA, CPIR — which need no
   legal opinion to begin and already constitute a useful spine.
4. **Decide the package name** and add it to `docs/shared-services.md` alongside
   `wegofwd-llm` and `wegofwd-video`.
