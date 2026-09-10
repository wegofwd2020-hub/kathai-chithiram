# KC-18 — Shared corpus package + Tier-1 spine

**Labels:** P1, knowledge-base, foundation
**Status:** 📋 Proposed — ungated; needs no clinician, no GPU, no new personal-data processing
**Refs:** `docs/ADR_009_knowledge_asset_and_surfaces.md` D1; `docs/ADR_011_corpus_rights_and_freshness.md` D1; `docs/KNOWLEDGE_BASE_PLAN.md` K0/K1; `docs/shared-services.md`

## Why
Three new audiences want answers, not animations. Building a chat surface before the
knowledge exists would produce fluent autocomplete over a domain where fluent-and-wrong is
the specific harm. The asset both products need is a rights-cleared, versioned, citable body
of practice knowledge.

It is also the one part of the expansion that can start today: no clinical collaborator, no
training run, no new personal data. And it pays back into the shipping product — grounded
generation (KC-21) is a real quality gain for stories.

## Acceptance criteria
- A shared in-process package in the `wegofwd` family, alongside `wegofwd-llm` and
  `wegofwd-video`, with its own canonical repo per `docs/shared-services.md`. Proposed name
  `wegofwd-arivu` (அறிவு, *knowledge*); the name is the owner's call.
- Ingestion, chunking, indexing and retrieval, with **every chunk carrying its source id,
  licence record reference and currency status**.
- **Tier-1 spine ingested:** CDC (incl. *Learn the Signs. Act Early.*), ED/IDEA/OSEP
  guidance, NIH/NICHD/IACC, CMS/Medicaid federal material, CPIR/parentcenterhub, Michigan
  statutes and administrative regulations.
- **Literature tier:** PMC Open Access Subset filtered to **CC0 and CC BY only**, retrieved
  through the permitted APIs (PMC Cloud, OAI-PMH, E-Utilities, BioC). CC BY-SA and CC BY-ND
  excluded pending legal review — ND is a genuine problem for a system that paraphrases.
- A Tier-3 source (ERIC full text, Cochrane, Campbell, WHO non-classification, paywalled
  journals) **cannot be ingested even when reachable**, asserted by test.
- The package holds **no personal data** and has no capability to store any (ADR-009 D6). It
  must not import Kathai Chithiram's store, cipher, consent or erasure modules.
- Coverage instrumentation from day one: the rate at which realistic questions find no
  supporting chunk is a reported **coverage metric**, not a defect discovered at the end.

## Implementation notes
- Start with the three sources needing no legal opinion — CDC, ED/IDEA, CPIR — which already
  constitute a useful spine while counsel reviews the wider tier list.
- Respect stated retrieval constraints: PMC requires the permitted APIs and NCBI rate limits
  (≤3 requests/sec, bulk off-peak). Do not bypass them.
- Chunk at a granularity that keeps a citation meaningful — a chunk should be quotable as
  support for a claim, not a whole document.
- Michigan statutes and regulations are free under the government edicts doctrine
  (*Georgia v. Public.Resource.Org*, 2020). Michigan **agency guidance** is not automatically
  free and needs its own check.
- OpenSpec docstrings; domain-specific errors, no bare `except`; Python ≥3.10 with
  `from __future__ import annotations`, ruff + mypy strict, matching this repo's conventions.

## Tests (fixtures only)
- A fixture source with no rights record is refused at ingestion.
- A Tier-3 fixture source cannot be ingested.
- A CC BY-NC or CC BY-ND fixture article is excluded from the literature tier.
- Retrieval returns chunks with source id, licence reference and status attached.
- The package imports nothing from `kathai_chithiram.storage`, `.access` or `.people`.
