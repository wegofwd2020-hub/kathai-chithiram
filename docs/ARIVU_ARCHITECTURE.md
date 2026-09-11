# wegofwd-arivu — Architecture Pattern

**The context dictionary: a citation-grounded knowledge and navigation asset, and the surfaces on top of it.**

Date: 2026-09-11 · Status: synthesis + proposal
Canonical home: this document describes the **`wegofwd-arivu`** corpus package and should
move there once that repo carries it (ADR-012 D4). It is drafted in `kathai-chithiram`
because that is where the shaping ADRs (ADR-006, ADR-009, ADR-013) live today.

> **How to read the status tags.** Every component is tagged:
> **`[DECIDED]`** — ratified or built, with the governing ADR named.
> **`[PROPOSED]`** — introduced in this document as a coherent design; **not** ratified.
> The agent layer and MCP integration are the main `[PROPOSED]` pieces — they are how the
> pattern would hang together, not settled decisions.
>
> **Diagram note.** This document specifies diagrams rather than drawing them. Each
> `▚ DIAGRAM SPEC` block is a precise, labelled description — components, colours, grouping,
> edges, legend — intended to be rendered in a design tool (Figma / Excalidraw / an image
> generator). No polished art is embedded here by design (owner's choice).

---

## 1. What this is

`wegofwd-arivu` (அறிவு, *knowledge*) is the **asset**: a curated, citable, versioned,
rights-cleared body of practice knowledge and government-regulation content about disability,
aging and accessibility. Everything a user ever sees is a **surface** on this asset. The
surfaces are replaceable; the asset is not. `[DECIDED — ADR-009 D1]`

The product's name for the asset is the **"context dictionary"**: given a scenario involving a
person with a disability (or an aging person), it assembles the relevant, cited possibilities —
what practices/accommodations exist, what a term means, what has been *allocated* by
government, what typically comes next — rather than answering a single question in isolation.
`[DECIDED — ADR-009 D8, Mission, D10]`

**The laws the whole architecture serves** (each is a hard gate, not a preference):
- **Educate, always cite, never advise.** Explain, cite, point to who-decides; never issue an
  individualised recommendation, eligibility determination, diagnosis or assessment. An answer
  with no retrieved source is not produced. `[DECIDED — ADR-009 D3]`
- **Navigate, never determine.** Surface programs, criteria-as-written, sources and who
  decides; never adjudicate a specific person's eligibility. `[DECIDED — ADR-009 D3/D10]`
- **No personal data.** Decline and redirect any query describing a specific real person; the
  asset holds none. `[DECIDED — ADR-009 D6]`
- **Risk-of-harm routes to a human.** A crisis is not a corpus answer; it escalates. No
  assistant surface ships until that path exists. `[DECIDED — ADR-009 D7]`
- **Facts live in the corpus, never in the model's weights.** The differentiator and the
  regulatory posture both depend on this. `[DECIDED — ADR-010]`

---

## 2. The layered architecture (the hero view)

Seven layers, bottom to top, with cross-cutting guardrails and observability beside them.

| Layer | Name | What it does | Status |
|---|---|---|---|
| **L0** | **Sources** | Federal regs (IDEA, CMS/Medicaid, SSA, ADA/EEOC, CDC), state material (Michigan first), practice literature, local resource directories | `[DECIDED — ADR-009 D4, ADR-011]` |
| **L1** | **Ingestion & provenance pipeline** | Fetch, chunk, attach rights records, stamp freshness/currency, tag entitlements | `[DECIDED — ADR-011]`; entitlement/benefit tagging schema `[PROPOSED]` |
| **L2** | **Corpus store** | Persist chunks + provenance + currency; full-text now, embedding-ready; the need-dependency graph | store `[DECIDED — arivu persistence spec]`; dependency graph `[PROPOSED]` |
| **L3** | **Retrieval (RAG)** | Lexical retrieval now, vector-ready; entitlement retrieval; dependency expansion; returns passages **with citations** | lexical/vector `[DECIDED — arivu spec]`; entitlement & dependency retrieval `[PROPOSED]` |
| **L4** | **LLM seam (`wegofwd-llm`)** | Provider-agnostic; constrained/structured output; consumes retrieved context; cite-or-refuse | `[DECIDED — ADR-006, KC-12, wegofwd-llm]` |
| **L5** | **Agent / orchestration layer** | Bounded workflow: understand → plan retrieval → retrieve → expand dependencies → compose cited answer → verify guardrails → escalate | `[PROPOSED]` |
| **L6** | **Surfaces** | (1) Kathai Chithiram animation; (2) the practice assistant; (3) the labelled commercial layer | animation `[DECIDED/built]`; assistant surface `[DECIDED, later — ADR-009 D5]`; commerce `[PROPOSED — ADR-013]` |
| **X** | **Cross-cutting: Guardrail/Policy engine** | Enforces the five laws as hard gates at intake and before output | `[PROPOSED]` (encodes `[DECIDED]` laws) |
| **X** | **Cross-cutting: MCP integration** | Expose the corpus as an MCP tool-server; optionally consume external MCP tools (live/local data) | `[PROPOSED]` |
| **X** | **Cross-cutting: Eval & observability** | Contract/rubric evals, the use-case log as eval set, citation-coverage & refusal metrics | eval harness `[DECIDED — ADR-006 D6]`; assistant eval `[PROPOSED]` |

```
▚ DIAGRAM SPEC — "Hero: the asset and its surfaces" (render as a layered stack)

LAYOUT: a vertical stack of horizontal bands, L0 at the bottom to L6 at the top,
        with two full-height side rails (left: Guardrail/Policy engine; right:
        Eval & Observability) hugging L3–L6, and a small MCP "plug" motif on the
        right edge of L3–L5.

BANDS (bottom → top), each a rounded horizontal block, colour by role:
  L0 Sources        — colour: slate/steel grey.   Icons inside: government building
                      (federal), state outline (Michigan), book (literature),
                      map-pin (local directories).
  L1 Ingestion      — colour: teal.   Icons: funnel, tag (rights), clock (freshness),
                      ribbon/seal (entitlement tag).
  L2 Corpus store   — colour: deep blue.   Icons: cylinder (DB), magnifier-index (FTS),
                      small node-graph glyph labelled "need-dependency graph (PROPOSED)".
  L3 Retrieval/RAG  — colour: indigo.   Icons: magnifier, quote-mark (citations),
                      branching arrows labelled "dependency expansion".
  L4 LLM seam       — colour: violet.   Icon: chip/brain; badge "provider-agnostic";
                      small lock badge "constrained / cite-or-refuse".
  L5 Agent layer    — colour: amber.   Icon: gears + a small flow of 6 dots
                      (the sub-steps); dashed border to signal PROPOSED.
  L6 Surfaces       — colour: warm green.   Three tiles side by side:
                      "Kathai Chithiram (animation)" [solid], "Practice assistant"
                      [solid, tagged 'later'], "Commercial layer" [dashed, tagged 'ADR-013'].

SIDE RAILS (full height beside L3–L6):
  LEFT  rail — red/maroon, vertical label "Guardrail / Policy engine":
        four small shields down its length labelled "cite-or-refuse",
        "navigate-not-determine", "no personal data", "risk-of-harm → human".
  RIGHT rail — grey-green, vertical label "Eval & Observability":
        glyphs "citation coverage", "refusal rate", "freshness", "use-case eval set".

MCP MOTIF: a small plug/socket icon on the right edge spanning L3–L5, labelled
        "MCP (PROPOSED): corpus exposed as tools ↔ external tools consumed".

EDGES: single upward arrows L0→L1→L2→L3→L4; L3 also feeds L5; L5 orchestrates
        L4 and L3 (draw L5 with two curved arrows down to L4 and L3) and emits to L6.
        The LEFT rail draws thin arrows INTO L5 intake and INTO the L5→L6 output
        (two gates). 

LEGEND: solid border = DECIDED; dashed border = PROPOSED. Colour key for the 7 layers.
```

---

## 3. Where AGENTS, LLM, RAG and MCP each fit

You asked specifically how these pieces relate. This is the one-screen answer.

| Piece | Role in wegofwd-arivu | Status |
|---|---|---|
| **RAG (retrieval-augmented generation)** | The **spine**. The model is never asked to *know* the answer — retrieval pulls cited passages from the corpus and hands them to the model as context. This is what makes answers current, cited, and correct instead of plausibly wrong. | `[DECIDED — ADR-010]` |
| **LLM (via `wegofwd-llm` seam)** | The **language faculty**, not the knowledge. Provider-agnostic seam; it reads retrieved context + the query and produces prose that only restates cited material, or refuses. Constrained/structured where structure matters (as in KC-12 for the animation surface). | `[DECIDED — ADR-006, wegofwd-llm]` |
| **Agents** | The **orchestrator**. A *bounded* workflow (not open-ended autonomy) that plans retrieval, follows dependencies, assembles the answer, and runs the guardrail checks. The domain forbids a free-roaming agent — cite-or-refuse and never-advise are hard gates the orchestration enforces deterministically. | `[PROPOSED]` |
| **MCP (Model Context Protocol)** | The **integration seam**. (a) Expose arivu's retrieval + entitlement lookup **as an MCP tool-server**, so any MCP-capable client (the surfaces, Claude, a partner's agent) can query the context dictionary as a tool — with citations attached. (b) Optionally **consume** external MCP servers for live/local data (e.g. a current local-clinic directory, a government API) the corpus can't hold statically. | `[PROPOSED]` |

**The one-line mental model:** *RAG fetches the cited facts → the agent orchestrates and guards
→ the LLM phrases → MCP is how other systems plug into all of it.*

---

## 4. Component deep-dives

### 4.1 Corpus store (L2) `[DECIDED core + PROPOSED graph]`
- **Does:** persists source records, chunks, provenance/rights, and currency; serves retrieval.
- **Today (decided):** embedded SQLite + FTS5, content-hash chunk IDs, reconciliation
  (added/unchanged/revived/superseded), a reserved `embedding` column for vector search later,
  `CurrencyStatus` incl. `WITHDRAWN` (arivu `feat/persistence-layer` spec).
- **Proposed evolution:** a **need-dependency graph** — edges between needs/topics ("solving X
  commonly requires Y next") so retrieval can follow dependencies, not just match passages. This
  is the "context" in context dictionary and the mechanism the Mission implies. `[PROPOSED — an ADR-010 evolution]`
- **Depends on:** the ingestion pipeline (L1) for content and provenance.

### 4.2 Ingestion & provenance pipeline (L1) `[DECIDED — ADR-011]`
- **Does:** fetch sources, chunk them, attach a **rights record** (tier, licence, attribution),
  stamp **freshness/currency** (regs and directories go stale — dating is safety-critical),
  and detect supersession.
- **Proposed add:** an **entitlement tagging schema** — for regulation sources, tag each
  benefit/program with `program · criteria-as-written · jurisdiction · who-decides · how-to-apply`
  so L3 can answer "what has been allocated for a situation like this?". `[PROPOSED — ADR-009 D10 names the requirement]`

### 4.3 Retrieval / RAG (L3) `[DECIDED core + PROPOSED extensions]`
- **Does:** given a scoped query, return the most relevant chunks **with their citations**;
  never returns uncited text to L4.
- **Modes:** lexical (FTS/bm25) now; vector/semantic when embeddings land; **entitlement
  retrieval** (query the benefit tags); **dependency expansion** (after answering the immediate
  need, retrieve adjacent/downstream needs from the graph). `[extensions PROPOSED]`
- **Guarantee it enforces:** if nothing relevant is retrieved, the answer is a refusal, not a
  guess (feeds the cite-or-refuse law).

### 4.4 LLM seam — `wegofwd-llm` (L4) `[DECIDED]`
- **Does:** provider-agnostic `complete(LLMRequest) -> LLMResponse`; privacy posture check +
  pseudonymisation guards live here (reused from the animation pipeline); constrained/structured
  output where a schema applies (KC-12). For the assistant, it is prompted to **restate only
  retrieved, cited context** and to refuse when context is thin.
- **Why a seam:** lets a local/owned model replace a frontier model later without changing
  callers (ADR-006 sovereignty argument), and keeps the surfaces provider-agnostic.

### 4.5 Agent / orchestration layer (L5) `[PROPOSED]`
A **bounded** workflow — deterministic control flow with the LLM and retrieval as tools, **not**
an autonomous agent. Sub-steps:
1. **Intake & scope** — classify the query; **guardrail gate**: is it a personal-person
   description (decline, D6)? a crisis (escalate, D7)? an eligibility-determination request
   (reframe to navigational)?
2. **Retrieval planning** — decompose into sub-queries (education vs navigation vs entitlement).
3. **Retrieve** — RAG over the corpus (L3); entitlement lookup where relevant.
4. **Dependency expansion** — given the immediate need, pull the "what comes next" set.
5. **Compose** — assemble the cited answer: Layer A (education), navigation (who-to-ask, local
   resources), and — assistant surface only — the labelled Layer B commercial strip (ADR-013).
6. **Verify (guardrail gate)** — every claim has a citation; no determination/advice; freshness
   dates present; jurisdiction correct. Fail → refuse or escalate; never emit ungrounded text.

### 4.6 Guardrail / Policy engine (cross-cutting) `[PROPOSED, encodes DECIDED laws]`
The five laws implemented as **hard gates** at two points (intake and pre-output), not as prompt
suggestions. Single enforcement surface for privacy (D6), scope (D3), determination (D10),
escalation (D7), and citation coverage.

### 4.7 MCP integration (cross-cutting) `[PROPOSED]`
- **arivu as an MCP server:** expose `retrieve`, `entitlement_lookup`, `dependency_expand` as
  MCP tools that return **passages with citations**. Any MCP client — the practice assistant,
  Kathai Chithiram's generation step, Claude, or a vetted partner — consumes the context
  dictionary the same way. Makes the asset reusable across the family and beyond.
- **arivu as an MCP client:** for data the corpus should *not* hold statically (a live local
  provider directory, a government status API), the agent layer calls an external MCP tool at
  request time — subject to the same freshness/citation rules.

### 4.8 Surfaces (L6)
- **Kathai Chithiram (animation)** `[DECIDED/built]` — consumes arivu for grounded generation;
  produces an artefact for a child; **no commerce, child data** (ADR-013 D1, ADR-001).
- **Practice assistant** `[DECIDED, ships later — ADR-009 D5/D7]` — direct query → cited answer
  for P2/P3/self-advocate personas; the primary home of entitlement discovery and dependency
  answering.
- **Commercial layer** `[PROPOSED — ADR-013]` — assistant-only, labelled, disclosed; money never
  bends Layer A.

---

## 5. Key flows (diagram specs)

### Flow A — a question becomes a cited answer (the core RAG + guardrail loop)
```
▚ DIAGRAM SPEC — "Flow A: query → cited answer" (horizontal swimlane, left→right)

NODES (rounded, colour by the layer they belong to, matching §2):
  [User query] (green) → [Intake & scope gate] (red, shield) →
  [Retrieval planner] (amber) → [RAG retrieve from corpus] (indigo, with a
  cylinder glyph feeding it) → [LLM compose, cite-only] (violet) →
  [Verify gate: every claim cited? no determination?] (red, shield) →
  [Cited answer + who-to-ask] (green).

BRANCHES (draw as red dashed arrows peeling off the two red gates):
  from Intake gate → [Decline: personal person] and → [Escalate: risk-of-harm → human].
  from Verify gate → [Refuse: no source] (loops back or ends).

ANNOTATION: under the RAG node, caption "facts from corpus, never from weights".
COLOUR KEY reused from the hero diagram.
```

### Flow B — entitlement discovery (Decision 10)
```
▚ DIAGRAM SPEC — "Flow B: entitlement discovery"

NODES left→right:
  [Query: "what are we entitled to?"] (green) →
  [Entitlement retrieval over tagged regs] (indigo; ribbon/seal glyph) →
  [Assemble: program · criteria-as-written · source · who-decides · how-to-apply] (violet) →
  [Freshness stamp + "verify with the agency"] (teal, clock glyph) →
  [Jurisdiction filter (Michigan-first)] (slate, state-outline glyph) →
  [Navigational answer] (green).

HARD-STOP CALLOUT: a large red bar UNDER the "Assemble" node reading
  "NEVER: 'you qualify' / 'you'll receive $X' — determination belongs to the agency"
  with an arrow to a green node [Hand-off to benefits counsellor] for the
  "so do I qualify?" follow-up.
```

### Flow C — dependency-aware / anticipatory answering (the Mission)
```
▚ DIAGRAM SPEC — "Flow C: dependency expansion"

CENTER node [Immediate need solved] (green). Around it, a RADIAL burst of
smaller nodes = the downstream/adjacent needs, each an amber node connected by
an edge labelled with the relationship. Worked example (use hearing aid):
  center: "Hearing aid selected"
  spokes: "recurring batteries", "dexterity to change them → rechargeable",
          "backup device", "audiology follow-ups", "phone/TV compatibility",
          "local clinic (live/MCP data)".
CAPTION: "the 'context' in context dictionary — the web of needs, not a lookup".
Each spoke node carries a small quote-mark glyph (still cited) and where relevant
a red 'navigate-not-determine' shield (e.g. the funding spoke).
```

### Flow D — grounded generation for Kathai Chithiram (surface 1)
```
▚ DIAGRAM SPEC — "Flow D: grounded animation generation"

NODES: [Parent story] (green) → [RAG: retrieve relevant practice] (indigo) →
  [LLM seam: constrained/structured scene-script (KC-12)] (violet, lock badge) →
  [Validate scene script] (red gate) → [Renderer] (green) → [Animation (mp4)] (green).
ANNOTATION: a padlock over the whole lane labelled "child data — no commerce,
  full privacy apparatus (ADR-001)". Contrast note: "this surface produces an
  artefact; the assistant surface produces a cited answer".
```

---

## 6. Decided vs proposed — summary

**Decided (ratified or built; ADR named):**
- Asset-and-surfaces model; "context dictionary" name; primary-goal framing — ADR-009 D1/D8.
- Educate/cite/never-advise; navigate-not-determine; no-PII; risk-of-harm escalation — ADR-009 D3/D6/D7/D10.
- Retrieval-first, facts-not-in-weights — ADR-010.
- Rights/freshness/jurisdiction regime; Michigan-first + federal — ADR-011, ADR-009 D4.
- Provider-agnostic LLM seam; constrained/structured decoding — ADR-006, KC-12, `wegofwd-llm`.
- Corpus persistence (SQLite+FTS, embedding-ready) — arivu `feat/persistence-layer` spec.
- Commercial-layer boundaries — ADR-013.
- Repo topology — ADR-012.

**Proposed (this document; needs ratification):**
- The **agent/orchestration layer** (bounded workflow, guardrails as hard gates).
- **MCP integration** (arivu-as-tool-server; consuming external MCP for live/local data).
- The **need-dependency graph** corpus data model (an ADR-010 evolution).
- The **entitlement tagging schema** (ADR-009 D10 names the requirement; schema undesigned).
- The **guardrail/policy engine** as a distinct enforcement component.

**Next step if you want these ratified:** each `[PROPOSED]` block is a candidate ADR in the
`arivu` repo (agent layer, MCP seam, dependency graph, entitlement schema). None is a
now-build — the corpus spine and grounding for the animation come first (ADR-009 D5), and the
assistant surface waits on the risk-of-harm path (ADR-009 D7).

---

## 7. Relationship to existing ADRs

- **ADR-006** — domain-model strategy (own the model over time); the LLM seam + constrained decoding.
- **ADR-009** — the asset and surfaces; the five laws; entitlement discovery (D10); the Mission.
- **ADR-010** — retrieval-first architecture (canonical copy in `arivu`); RAG, dependency graph.
- **ADR-011** — corpus rights and freshness (canonical copy in `arivu`).
- **ADR-012** — repository topology (why arivu is its own repo; where this doc belongs).
- **ADR-013** — the practice-assistant surface and its commercial model.
- **Use-case log** (`docs/CONTEXT_DICTIONARY_USE_CASES.md`) — the scenarios this architecture serves and the future eval set.
