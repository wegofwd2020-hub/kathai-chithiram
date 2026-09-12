# WeGoFwd — State of Play

**As of:** 2026-09-12 · **Owner:** Sivakumar (Siva) Mambakkam · **Purpose:** the **front door** to the whole
project — the high-level view of *what we're building, where everything lives, what's built,
what's next, and who each remaining item is blocked on*, so the next move is never ambiguous.

> **This is a map, not a spec.** It orients and links; it does not duplicate. The authoritative
> detail lives in the ADRs (`docs/ADR_INDEX.md`), the architecture (`docs/ARIVU_ARCHITECTURE.md`),
> `docs/DPIA.md`, `PRIVACY.md`, and `TICKETS/`. When a decision hardens, it becomes an ADR and
> this file just points to it. Half-formed thoughts live in **§ Open threads** until they do.

---

## 1. North star

**We are building a "context dictionary":** a citation-grounded, *never-advise* knowledge and
navigation asset for people with disabilities, seniors, and the people who help them. Given a
real scenario, it assembles the relevant, **cited** possibilities — what practices and
accommodations exist, what a term means, **what the government has already allocated**, and
**what comes next** — and points to who decides. It never diagnoses, never determines
eligibility, never gives individualised advice.

**Mission:** *address the person, not the label* — serve the immediate need **and** the
dependencies that solving it creates, instead of answering the one question in front and stopping.

---

## 2. The shape — one asset, many surfaces

The **corpus is the asset** (the context dictionary); everything a user sees is a **surface** on
it. Surfaces are replaceable; the asset is not. `[ADR-009]`

- **Surface 1 — Kathai Chithiram (animation).** A parent's story → a calm, captioned animation a
  special-needs child can understand. **Built and shipping.** It consumes the corpus for grounded
  generation. No commerce, full child-data privacy apparatus.
- **Surface 2 — the practice assistant (later).** Direct question → cited answer for carers,
  helper-learners, self-advocates, seniors. Home of entitlement discovery and dependency-aware
  answering. Ships **after** the animation and **after** the risk-of-harm escalation path exists.
- **The asset — `wegofwd-arivu`.** A curated, rights-cleared, versioned corpus + retrieval (RAG).
  **Federal Tier-1 spine ingested** (CDC, ED/IDEA-OSEP, NIH, CMS/Medicaid, CPIR, Michigan — 6/6
  families, ~278 cited chunks) and the **entitlement-discovery layer is built** (ADR-009 D10:
  program · criteria-as-written · jurisdiction · who-decides · how-to-apply, cite-or-refuse,
  navigate-never-determine). State/nonprofit content is copyright-gated. Its own repository.

**Architecture:** `docs/ARIVU_ARCHITECTURE.md` (7-layer pattern: sources → ingestion → corpus →
RAG → LLM seam → agent layer → surfaces; with rendered diagrams).

**The five laws** (hard gates, every surface inherits them — ADR-009 D3/D6/D7/D10, ADR-010):
educate/cite/never-advise · navigate-never-determine · no personal data on the assistant ·
risk-of-harm routes to a human · facts live in the corpus, never in model weights.

---

## 3. Where everything lives (doc map)

| You want… | Read |
|---|---|
| The decisions (the "why") | `docs/ADR_INDEX.md` → ADR-001…013 |
| Product/strategy north star | **ADR-009** (asset & surfaces, context-dictionary, mission, entitlement discovery) |
| How it's built (RAG / LLM / agents / MCP) | `docs/ARIVU_ARCHITECTURE.md` |
| The scenarios it serves (+ future eval set) | `docs/CONTEXT_DICTIONARY_USE_CASES.md` (UC-1…UC-13) |
| Who else is in the market | `docs/COMPETITIVE_LANDSCAPE.md` |
| The domain-model / LLM programme | **ADR-006**, `docs/LLM_PROGRAM_PLAN.md` |
| The scene-script contract | `docs/SCENE_SCRIPT_CONTRACT.md`, **ADR-007** |
| Corpus retrieval / rights / freshness | **ADR-010**, **ADR-011** (canonical copies in `wegofwd-arivu`) |
| Commercial model boundaries | **ADR-013** |
| Privacy / safety / compliance | `PRIVACY.md`, `docs/CONTENT_SAFETY.md`, `docs/DPIA.md`, `docs/DPO_REVIEW_PACKAGE.md` |
| The clinician engagement | `docs/M1_PROFESSIONAL_COLLABORATOR_BRIEF.md`, `docs/M1_OUTREACH_SEND_READY.md` |
| Repo topology (why arivu is separate) | **ADR-012** |

---

## 4. Status by track

| Track | State | Blocked on |
|---|---|---|
| **Animation pipeline (Surface 1)** | **Built, green — 735 tests.** Contract + validation, generation behind `wegofwd-llm`, both renderers, narration/sfx/transitions/captions, offline mode, content-aware art. | — (buildable polish only) |
| **KC-12 constrained decoding + v2 emission** | **Done, merged.** Structured output + v2 scene-script; validate-and-repair retained. | — |
| **KC-21 retrieval grounding** | **Wired + live.** Generation grounds scene scripts in cited corpus passages (pseudonymised query, additive, fails safe). Verified end-to-end against the ingested corpus; `KC_ARIVU_DB` set. | — |
| **M3 domain model (own the model over time)** | Contract (KC-13) + constraint (KC-12) done. Next is validators (KC-16). | **Clinician** (narrative policy) |
| **M1 progress engine** | Built to the line; inert without a policy. | **Clinician** (ProgressPolicy) |
| **The corpus (`wegofwd-arivu`)** | **Built.** SqliteCorpus + FTS5 retrieval + rights/currency regime (merged); **federal Tier-1 spine ingested (6/6, ~278 chunks)**; TLS-chain + stale-URL fixes shipped. | — for **federal** (done); permissions for state/nonprofit; PDF extractor + Tier-2 PMC + retraction daemon still unbuilt |
| **Entitlement discovery (ADR-009 D10)** | **Built, merged.** Schema + cited TOML registry (3 verbatim-cited federal programs: IDEA Part C, IDEA Part B, Medicaid HCBS 1915(c)) + fail-closed loader + `EntitlementIndex.find`; navigate-never-determine locked by a guard test. | — (EPSDT/SSI deferred pending citable/ingestable source content) |
| **Practice assistant (Surface 2)** | Framed (ADR-009), **not designed/built.** | Animation shipping + **risk-of-harm path** (ADR-009 D7) |
| **Commercial layer** | Boundaries set (ADR-013), nothing built. | **Counsel** (FTC / device-promotion) + owner's model choice |
| **Platform accounts / DOB** | Built against synthetic identities. | **DPO** sign-off before real child data |

---

## 5. What's next — and who each is blocked on

**Buildable now, no one's permission needed:**
- **Deepen the corpus:** a PDF extractor (unlocks Michigan admin rules + gov PDFs), Tier-2 PMC
  open-access literature, and a retraction/withdrawal watch (ADR-011). Each widens grounding and
  entitlement coverage.
- **Grow the entitlement map:** more federal programs and jurisdictions as source content lands;
  re-add **EPSDT** (needs richer CMS content) and **SSI** (needs honest SSA access — SSA.gov's WAF
  blocks the crawler; candidate path is citing 20 CFR 416 via eCFR).
- Animation-product polish and the ADR-007 step-6 rename tidy-ups.

**Blocked on a person (external — the real unlocks):**
- **A retained clinical collaborator** → unblocks KC-16 (narrative policy), KC-14/15 (corpus
  adjudication), and the M1 progress engine. *One engagement covers both tracks.* Outreach is
  drafted and send-ready.
- **A data-protection / legal review** → ADR-005 accounts+DOB, ADR-011 source tiering, ADR-013
  commercial model.
- **A deployment boundary** → last step of ADR-004.

**Honest note:** the corpus is now real code shipping — persistence, the ingested federal spine,
live retrieval grounding, and the entitlement-discovery foundation all merged. The single biggest
lever for the *animation/clinical* tracks is still **retaining the clinician**; the corpus/asset
track can keep advancing without it.

---

## 6. Open threads — thoughts not yet decided

Live thinking that has a home here until it hardens into an ADR (in `wegofwd-arivu` where noted):

- **Agent / orchestration layer** — bounded workflow, guardrails as hard gates (proposed in the
  architecture doc; candidate arivu ADR).
- **MCP integration** — expose the corpus as an MCP tool-server; consume external MCP for
  live/local data (candidate arivu ADR).
- **Need-dependency graph** — corpus data model for anticipatory answering (an ADR-010 evolution).
  (The entitlement tagging schema this thread once named is now **built + merged** — see §4.)
- **Commercial model choice** — affiliate vs sponsored vs marketplace; v1-or-later; commerce vs
  subscription/grant (a values call). Owner's, gated on counsel (ADR-013).
- **Scope breadth confirmation** — disability + aging + accessibility is set as vision (ADR-009
  D9); confirm the domain order as the corpus grows.
- **Wider shared services** — `wegofwd-video`, `wegofwd-secure` (see `docs/shared-services.md`).

---

*Update this file when a track changes state or an open thread becomes a decision. Keep it a
one-screen map — push detail down into the ADRs and specs it links to.*
