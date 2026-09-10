# KC-19 — Rights records, and attribution rendered from them

**Labels:** P1, knowledge-base, legal
**Status:** 📋 Proposed — counsel review of the tier list is a precondition for volume ingestion
**Refs:** `docs/ADR_011_corpus_rights_and_freshness.md` D2, D3, D5, D6; `docs/ADR_010_retrieval_first_practice_assistant.md` D2

## Why
Two traps decide most of the hard cases in this domain, and both are easy to walk into:

- **"Free to read" is not "licensed for reuse."** ERIC, PubMed, NICE and Cochrane are all
  freely readable and none broadly permits commercial redistribution. Cochrane's publisher
  expressly reserves rights for text and data mining and for AI training.
- **"Federally funded" is not "federally authored."** 17 U.S.C. §105 covers works of federal
  *employees*. Under 2 CFR 200.315(b) a grantee retains copyright and the agency reserves a
  licence *for federal purposes* — which runs to the government, not to us. This is why the
  most valuable practice layer in the field (AFIRM) is the one we may not take.

Separately, licence obligations force the architecture ADR-010 already chose for safety
reasons: CC BY requires attribution and CDC requires a non-endorsement disclaimer, and
neither is satisfiable by a model answering from weights. **The obligations and the safety
design point the same way.**

## Acceptance criteria
- A rights record per source: canonical URL, publisher, licence identifier, **verbatim terms
  text or a dated quotation of it**, tier, attribution string, required disclaimers,
  retrieval date, verifier, verification date, and any derivative or commercial restriction.
- **Ingestion refuses a source without a rights record.** A source whose terms could not be
  determined is recorded as *unclear — needs legal review* and **excluded**. "No licence
  stated" is not permission.
- Attribution and disclaimers are **rendered with the answer, derived from the record** —
  not a credits page. Where CC BY requires attribution it appears with the claim it supports;
  where a federal source requires a non-endorsement disclaimer it is carried. **Federal
  agency logos and marks are never used.**
- An ND-licensed chunk (e.g. WHO classifications, CC BY-ND) is served **verbatim only** and
  never paraphrased, because generated paraphrase is arguably an adaptation.
- `docs/CORPUS_RIGHTS.md` — the living register, versioned in-repo so a tier change is
  reviewable in a diff.
- **Verification debt closed** (items the survey could not establish, to be settled not
  assumed): AFIRM/NPDC terms (none published anywhere on the site); an explicit NIH/IACC
  copyright notice; the CMS website-policies notice; AAP permissions terms; ERIC's own
  copyright page; per-site terms for individual state PTIs and UCEDDs.
- **AFIRM/NPDC handling (ADR-011 D5):** not ingested. Default to route 2 — cite AFIRM as a
  pointer and author original procedural text against the underlying primary studies, since
  the *findings* (which practices have an evidence base) are facts while the modules'
  *expression* is protected. Pursue a written FPG licence in parallel; it costs an email.
- Per-state onboarding includes a rights review. State posture varies sharply — Florida and
  New Jersey treat public records as freely reproducible including commercially; Arizona,
  Pennsylvania and New York assert copyright in state works.

## Implementation notes
- Capture terms text verbatim at retrieval time. Sites change; a dated quotation is the
  evidence, a link is not.
- Keep the register human-reviewable. Its value is that a lawyer can read it.
- The safe core of the literature tier is **CC0 + CC BY**. CC BY-SA raises a copyleft
  question for generated output and CC BY-ND the derivative question above; both need legal
  review before inclusion, not a judgement call in code.
- OpenSpec docstrings; no bare `except`.

## Tests (fixtures only)
- Ingestion refuses a fixture source with no rights record, and one marked *unclear*.
- Rendered attribution and disclaimer for a chunk match its rights record exactly.
- An ND-licensed chunk is emitted verbatim; a paraphrasing path over it fails.
- A federal-source answer carries the non-endorsement disclaimer and no agency mark.
- The register and the index cannot disagree: every indexed source id resolves to a record.
