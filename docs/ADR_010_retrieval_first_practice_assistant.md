# ADR-010 — Retrieval-first: facts live in the corpus, never in the weights

**Date:** 2026-09-10
**Status:** Proposed
**Branch at decision:** main

---

## Context

ADR-006 decided that the story generator's missing capability should be reached by adapting
a small permissively-licensed base with a LoRA — capability C4, situational judgement, is
genuinely learned. The obvious move is to apply the same answer to the practice assistant
ADR-009 scopes.

**That would be wrong, and this ADR records why the two tracks diverge.** The divergence is
not inconsistency; it follows from ADR-006's own decomposition. The generator's hard problem
is *judgement over a fixed contract* — no external fact is needed to decide that a story
about a dental visit should be six scenes rather than twelve. The assistant's hard problem
is the opposite: almost every useful answer is a **claim about the world** — what the
evidence says, what a regulation requires, what a state's waiver covers, what changes at
age 22 — and the model's judgement is nearly irrelevant next to whether the claim is true,
current, and attributable.

Five properties are required of every claim the assistant makes. A fine-tuned model provides
none of them:

| Requirement | Facts in weights | Facts in a retrieved corpus |
|---|---|---|
| **Citable** — the reader can check the basis | No. There is no basis to show | Yes, by construction |
| **Updatable** — a state changes a waiver rule | No. Requires retraining | Yes. Re-ingest one document |
| **Retractable** — OSEP withdraws guidance; AAP retires a report | No. It stays in the model | Yes. Tombstone it |
| **Attributable** — CC BY requires attribution; CDC requires a non-endorsement disclaimer | No. Licence obligations are unsatisfiable | Yes. Carried on the chunk |
| **Auditable** — "why did it say that?" | No | Yes. The retrieved set is the answer |

The attribution row deserves emphasis because it is the one that is usually missed: **the
corpus's own licence terms make retrieval mandatory, independently of any safety argument.**
Ingesting CC BY literature into a fine-tune produces a model that cannot attribute, which is
a licence breach, not a quality shortfall. The obligations and the safety architecture point
the same way, which is a good sign that the architecture is right.

And the regulatory driver from ADR-009 D3 lands here as a concrete design constraint. FDA's
revised clinical-decision-support guidance turns on whether a professional can independently
evaluate the *basis* for a recommendation, with recommendations grounded in well-understood
and accepted sources rather than a proprietary algorithm. A citation-grounded retrieval
system satisfies that criterion by construction; a model answering from weights structurally
cannot, because there is nothing to review.

## Decision

**Decision 1 — Facts live in the corpus. Never fine-tune facts into the model.**
No pretraining, no continued pretraining and no supervised fine-tuning whose purpose is to
put domain *content* into weights. The model's job on this track is to read retrieved
passages and compose a faithful, plainly-worded answer over them — nothing more. This holds
regardless of how good a domain fine-tune looks in a demo, because the failure mode it
creates is invisible: a confidently wrong uncited claim is indistinguishable from a correct
one at the point of reading.

**Decision 2 — Citation is the safety architecture, not a UI feature. No support, no
answer.**
Every substantive claim in an answer must be traceable to a retrieved chunk. Where retrieval
returns nothing that supports a claim, the system does not produce the claim — it says what
it does not know and points to who would. **"I don't have a source for that" is a
first-class, correct output**, in the same way `IndicatorState.INSUFFICIENT_DATA` is a
first-class state in `progress/engine.py` rather than an error.

**Decision 3 — A deterministic-first scope router runs before retrieval.**
Four classes; only the first is answered:

1. **In-scope educational question** → retrieve, compose, cite.
2. **Out-of-scope** (unrelated domain, or a question about a named individual per ADR-009
   D6) → decline and redirect. Not answered, **not stored**.
3. **Individualised advice or eligibility determination** ("does my son qualify," "should we
   try X for her") → decline the determination, offer the *general* educational answer plus
   who decides. This is ADR-009 D3's line, enforced at the input rather than hoped for in
   the output.
4. **Risk of harm** → the `CONTENT_SAFETY.md` §4 path: route to a person and to real
   resources.

Pattern-based rules run first and a model-assisted classifier second, because a
deterministic rule is testable at its boundary and a classifier is not. Per ADR-001 D5 the
router **detects and routes; it never triages and never decides**, and class 4 is
recall-biased — over-routing to a human is a cost, under-routing is a harm.

**Decision 4 — The answer has a contract, validated before display.**
The scene script is the contract between generation and rendering; the assistant needs the
same discipline. An answer is a structured object — claims, each carrying one or more
citations to retrieved chunks; the scope class that produced it; explicit limits ("this is
Michigan-specific," "this guidance was revised in 2022"); and a **next step naming a human
or an organisation**. Validation before display: a claim sentence with zero citations fails,
a citation to a chunk not in the retrieved set fails, an answer in scope class 2–4 carrying
substantive claims fails. Invalid answers are not repaired into existence; they are
withheld, exactly as `validate_scene_script` rejects rather than repairs.

The "next step" field is not decoration. For P2 and P3 the honest answer to most real
questions ends with a person — a case manager, a PTI, a school district, a clinician — and
a system that never surfaces one is quietly positioning itself as the answer.

**Decision 5 — Freshness is a first-class requirement, and supersession matters more than
staleness.**
Withdrawn federal guidance and retired clinical reports are more dangerous than merely old
content, because they read as authoritative while being wrong. The corpus therefore needs
**tombstone and supersession records**, not just a re-crawl schedule (ADR-011 D4): a
retrieved chunk whose source has been withdrawn, retracted or superseded must be either
suppressed or served with its status stated. A retracted study surfaced without its
retraction is the worst single output this system can produce.

**Decision 6 — What fine-tuning *is* for on this track: register and refusal, never facts.**
There is a legitimate later role for a tuned adapter here — answering a volunteer in plain
language and a BCBA in technical register, and refusing out-of-scope requests reliably and
gracefully. Both are *behaviours*, learnable from synthetic examples, and neither puts a
claim about the world into weights. **Deferred** until the corpus and retrieval demonstrably
work; a tuned refusal style over a bad corpus is polish on the wrong object.

**Decision 7 — Evaluation axes, extending the `kc eval` shape from ADR-006 D6.**
1. **Groundedness** — every claim traceable to a retrieved chunk that actually supports it.
   Measured by sampled human check, not by self-report.
2. **Citation accuracy** — the cited source says what the answer says it says. A correct
   answer with a wrong citation is a failure, because Decision 2 makes the citation the
   safety mechanism.
3. **Refusal correctness** — an adversarial suite of individualised-advice, eligibility,
   out-of-scope and risk-of-harm questions, scored on routing to the right class. Recall on
   class 4 reported separately and never traded against precision.
4. **Freshness** — the system never serves withdrawn, retracted or superseded content as
   current.
5. **Coverage and honest refusal** — how often the corpus genuinely lacks an answer, so that
   "I don't know" is measured as coverage rather than mistaken for a defect.

Notably there is **no clinical-preference axis**, because the system does not advise. That
is a deliberate consequence of ADR-009 D3 and a real saving in scarce clinician hours.

**Decision 8 — Prohibitions.**
- **No scraped user-generated content** — forums, social media, parent groups. Copyright and
  platform terms aside, it is health information about identifiable people, frequently
  minors, who never consented (ADR-011 D7).
- **No assessment-instrument content** — items, scoring tables, cut-offs, protocol text.
  Describing what an instrument is and citing published literature about it is fine.
- **No individualised output**, in any scope class (ADR-009 D3).
- **No storage of a question that describes a real person** (ADR-009 D6). Retention of
  question text at all is opt-in and defaults off; a "helpful" query log is how a
  no-personal-data system acquires personal data.
- **The model never adjudicates harm** (ADR-001 D5).

## Consequences

### Positive

- Every claim can be checked, updated, retracted and attributed — which is simultaneously
  the safety property, the licence-compliance property and the regulatory property. One
  architecture satisfies all three.
- Correcting an error is a document re-ingest, not a retraining run: minutes, not weeks, and
  no GPU.
- The system's competence grows by adding sources rather than by training, so the marginal
  improvement is librarian work a solo builder can do.
- Refusing well is designed in from the start rather than retrofitted, and "I don't have a
  source" is a state the architecture is built to express.
- Dropping the clinical-preference axis removes the most expensive evaluation input.

### Negative

- Retrieval quality becomes the whole product. Chunking, indexing, and above all
  **coverage** now determine whether the thing is useful, and a thin corpus produces a
  system that refuses constantly and feels useless.
- Citing everything makes answers longer and more hedged than a chat product users are
  accustomed to. That is the correct trade here and it is still a product-design problem.
- Two divergent ML strategies in one family — tuned generation, retrieved answers — is more
  to explain and more to keep straight. The decomposition in ADR-006 is what makes it
  coherent; without that framing it reads as inconsistency.
- The answer contract, the scope router and the freshness regime are substantial
  engineering before a single answer is served.
- Recall-biased harm routing will over-trigger. That is the intended direction of error and
  it will still be irritating.

### Neutral

- Embedding model, index and chunking strategy are implementation choices behind the corpus
  package; this ADR fixes the contract, the router and the evaluation axes.
- The composing model can be the frontier provider, the ADR-006 local model, or both behind
  the existing `LLMProvider` seam — Decision 1 constrains what is in the weights, not whose
  weights they are.

## Alternatives considered

- **Fine-tune a domain expert model on the literature.** Rejected: unciteable, unupdatable,
  unretractable, unattributable, and structurally unable to satisfy the independent-review
  criterion. It is also the approach that demos best and fails worst, which is why it needs
  an explicit rejection rather than silent avoidance.
- **Retrieval plus a fine-tune "for domain fluency."** Rejected as written: in practice it
  smuggles facts into weights, and the resulting uncited claims are indistinguishable at
  read time from grounded ones. Decision 6 keeps the legitimate part — register and
  refusal — and names it narrowly.
- **Let the model answer from general knowledge when retrieval returns nothing.** Rejected.
  This is the single most tempting shortcut and it converts every coverage gap into a
  confident fabrication, precisely where the user cannot tell.
- **Citations as a UI affordance, generated after the answer.** Rejected: post-hoc citation
  finds sources that look like they support a claim the model already made. The claim must
  come from the source, not the source from the claim.
- **Skip the scope router; handle scope in the system prompt.** Rejected: a prompt
  instruction is not testable at its boundary, and scope here is a legal boundary, not a
  stylistic one.
- **Serve superseded content with a date and let the reader judge.** Rejected for withdrawn
  and retracted material; acceptable, with status stated, for merely older material. The
  distinction is the whole of Decision 5.

## Migration / rollout

- **Not yet started.** Proposed; blocked on ADR-009 acceptance and the Tier-1 corpus.
- **Ratification condition (Proposed → Accepted):** the answer contract and scope router
  implemented and tested against an adversarial suite, over the Tier-1 spine, with the
  evaluation axes reporting — i.e. the refusal behaviour is proven before any answer is
  served to a real user.
- **Order:** corpus spine (`KC-18`) → rights and attribution (`KC-19`) → freshness and
  supersession (`KC-20`) → grounding for story generation (`KC-21`, the first real consumer
  and a low-risk way to prove retrieval) → risk-of-harm path → scope router and answer
  contract → assistant surface.
- Grounding the *story generator* first is deliberate: it exercises retrieval end to end
  behind an existing human review gate, so retrieval quality is proven where a mistake is
  caught before it reaches anyone.
- **Docs on acceptance:** `docs/CONTENT_SAFETY.md` (a section for the assistant surface —
  its MUST/MUST-NOT set is different from the story one and must not be conflated),
  `docs/DPIA.md` (record that the corpus holds no personal data, and that question retention
  defaults off), `docs/KNOWLEDGE_BASE_PLAN.md`.
- **Tests (synthetic questions only):** an answer with an uncited claim is withheld; a
  citation outside the retrieved set is rejected; each scope class routes correctly on a
  fixture suite, with class 4 recall asserted; a tombstoned source is never served as
  current; a question naming an individual is declined and not written anywhere.
