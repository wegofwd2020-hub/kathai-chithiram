# KC-21 — Ground story generation in the corpus

**Labels:** P1, quality, knowledge-base
**Status:** 📋 Proposed — depends on KC-18; the first real consumer of the corpus
**Refs:** `docs/ADR_009_knowledge_asset_and_surfaces.md` D1; `docs/KNOWLEDGE_BASE_PLAN.md` K3; `generation/generator.py`, `wegofwd_llm/gateway.py`

## Why
The corpus exists to serve two consumers, and the story generator is the one that already
ships. Today a story about a first dental visit is written from a general model's priors
about dental visits. Grounded in published desensitisation practice, it can be written from
what the field actually knows — the same story, but specific in the ways that make a social
narrative work.

This is also the **cheapest honest test of retrieval quality**. It exercises ingestion,
chunking, retrieval and relevance end to end in the one place where a mistake is caught
before it reaches anyone, because the KC-7 human review gate is already in the path. If
retrieval is poor, this is where that is discovered — for the price of a few weeks, and
before any answer surface is built on top of it.

## Acceptance criteria
- Generation retrieves supporting passages for the story's situation and conditions on them,
  behind the existing `LLMProvider` seam.
- **Pseudonymisation is unchanged.** Retrieval is driven by the *situation*, never by the
  child's identifiers: the query is built from the pseudonymised story text, and
  `gateway.run_generation`'s residual-identifier hard stop still fires before any dispatch.
  Corpus retrieval must not become a side channel around KC-2.
- Retrieved source ids are recorded against the generated scene script, so a reviewer (and a
  later audit) can see what informed it. Source ids only — no corpus text is copied into the
  stored script.
- **The human review gate is unchanged** (KC-7, `CONTENT_SAFETY.md` §6). Grounding is not an
  argument for automating approval.
- Grounded generation is **no worse** on the `kc eval` axes (KC-14) and better on domain
  specificity. If it is worse, retrieval is not ready and this does not ship.
- Graceful degradation: when retrieval returns nothing relevant, generation proceeds
  ungrounded exactly as today rather than failing. A story is not blocked because the corpus
  is thin — but the ungrounded rate is **reported**, because it is the corpus coverage metric
  in disguise.
- Licence constraints hold through the generator too: an ND-licensed passage may inform
  retrieval ranking but must not be paraphrased into narration.

## Implementation notes
- Build the retrieval query from the pseudonymised story text plus the inferred setting, not
  from raw intake.
- Keep grounding on the *generation* side of the contract boundary. `CLAUDE.md`'s rule
  stands: generation emits a valid scene script; renderers consume it. Retrieval does not
  reach the renderer.
- Report ungrounded rate per scenario type; that breakdown is what tells you which parts of
  the corpus to deepen next.
- OpenSpec docstrings; no bare `except`; never log retrieved text alongside story text.

## Tests (mock data only)
- The retrieval query contains no identifier from `NameMapping`, asserted on a fixture with
  a distinctive mock name.
- The residual-identifier hard stop still fires with grounding enabled.
- Retrieval returning nothing produces the same script as today's ungrounded path.
- Retrieved source ids are recorded against the script; no corpus text is persisted in it.
- An ND-licensed fixture chunk is not paraphrased into narration.
