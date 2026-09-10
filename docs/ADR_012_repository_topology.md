# ADR-012 — Repository and documentation topology: where the corpus, the assistant and the ADRs live

**Date:** 2026-09-10
**Status:** Proposed
**Branch at decision:** main

---

## Context

ADR-009 widened the scope from one product to one asset with two surfaces. Three things now
exist or are proposed:

1. **Kathai Chithiram** — built, shipping-adjacent, blocked only on external sign-offs.
2. **The practice knowledge corpus** — proposed (`KC-18`), ungated, buildable now.
3. **The practice assistant surface** — proposed, deliberately deferred until Kathai
   Chithiram ships and the risk-of-harm path exists (ADR-009 D5, D7).

The open question is structural: does the corpus become a folder inside
`kathai-chithiram`, a separate repository, or something else — and as the family grows,
where do the ADRs live so that a cross-cutting decision is findable exactly once?

There is a real pull toward a single repository. The project is a solo build; one repo means
one CI pipeline, one dependency file, one place to look. "Start together, extract when it
hurts" is a legitimate strategy and it is often the right one.

It is not right here, and the reason is not code coupling.

## Decision

**Decision 1 — The corpus gets its own repository, from the start.**
The decisive test is dependency direction: **`kathai-chithiram` will import the corpus**
(`KC-21`, retrieval-grounded generation). A dependency cannot live inside its own dependent
without inverting the relationship.

This is also a pattern the family already runs. `docs/shared-services.md` designates
`wegofwd-llm` as the canonical home for platform services, "every product consumes that
package in-process," and `pyproject.toml` already pins
`wegofwd-video @ git+https://github.com/wegofwd2020-hub/wegofwd-video@v1.0.0`. The corpus is
the third member of that set, not a feature of the first consumer that happened to need it.

**Decision 2 — Reject the subfolder. Its real cost is the privacy and legal posture, not the
build.**
A `corpus/` directory inside `kathai-chithiram` would give the costs of separation with none
of its benefits — coupled CI (the story product's suite running corpus ingestion), one
release cadence for two things whose cadences differ by an order of magnitude (the scene
contract changes rarely; the corpus re-ingests monthly, per ADR-011 D4), and entangled
history at the eventual split — without the tooling that makes a real monorepo work.

But the argument that decides it is this: **the corpus holds no personal data, and must be
able to demonstrate that.** ADR-009 D6 states it explicitly and `KC-18` asserts it by test.
Placing it inside a repository whose `CLAUDE.md`, `PRIVACY.md` and `DPIA.md` are entirely
about one child's special-category data muddies that claim from day one — not in code, but
in the answer to "what does this system process?", which is a question a DPO, a school
district or a funder will actually ask.

Unlike code coupling, this cost is invisible until someone asks, and "we will separate it
later" is precisely the kind of intention that does not survive contact with a shipping
deadline. Separation here is a statement about data, and it should be true from the first
commit.

**Decision 3 — The assistant surface gets its own repository, but not yet. Do not create it.**
It will be a separate repository for the same reasons, plus a different one: it has a
different user, a different content-safety rule set (ADR-010's MUST/MUST-NOT set is not the
story one and must not be conflated), and a different regulatory surface.

But creating it now — even empty, even as a placeholder — is a commitment device pointing
the wrong way. ADR-009 D5's whole point is that the surface waits. An empty repository with
a README is an invitation to start, and the risk this expansion carries is dilution. Create
it when `KC-18` is done, Kathai Chithiram has shipped, and the risk-of-harm path exists.

**Decision 4 — An ADR lives with the code it governs; a scope ADR lives where the scope
changed.**

| ADRs | Home | Reason |
|---|---|---|
| **001–008** | `kathai-chithiram` | They govern the story product — its safeguarding stance, its progress engine, its access control, its contract, its generation model |
| **009** | `kathai-chithiram` | It is the decision that *this product's boundary moved*. A scope ADR belongs where the scope was, not where the new thing landed |
| **010, 011** | **Move to the corpus repo** when `KC-18` creates it | They govern the corpus: its retrieval architecture and its rights regime. Leave a one-line pointer stub behind, exactly as `docs/shared-services.md` already does — "products link here rather than each keeping a copy" |
| **012** (this one) | `kathai-chithiram` for now | Family-level. Once a second repo exists, consider moving family-level architecture decisions to `wegofwd-llm/docs`, which `shared-services.md` already designates as the canonical architectural home |

**Decision 5 — Move nothing until the second repository exists.**
Splitting documentation before there is a second place to put it creates cross-references to
nowhere. `KC-18` creates the corpus repo; the ADR-010/011 move happens in that same change,
with pointer stubs, and not before. Staged, not big-bang.

**Decision 6 — Keep one ADR number sequence across the family.**
`ADR-011` means one thing regardless of which repository it currently sits in. Per-repo
sequences would produce two `ADR-001`s and make every cross-reference ambiguous, and
renumbering later is worse than a sequence that spans repositories. A single index
(`docs/ADR_INDEX.md`) lists all of them with their current home, and moves with the family.

## Consequences

### Positive

- The corpus's "no personal data" claim is structurally true and demonstrable, rather than
  asserted inside a repository that says the opposite on every other page.
- The dependency graph reads correctly: products depend on shared packages, in the pattern
  already established by `wegofwd-llm` and `wegofwd-video`.
- Each repository keeps a coherent release cadence — a corpus re-ingest does not version the
  story product, and a scene-contract change does not version the corpus.
- The ADR-placement rule is simple enough to apply without thinking about it, and the single
  number sequence keeps every cross-reference stable.
- Not creating the assistant repository keeps the sequencing decision honest.

### Negative

- Three repositories is more overhead for a solo builder: three CI configs, three dependency
  files, and cross-repo changes that need two pull requests and a version bump. This is a
  genuine, recurring tax and it is being accepted deliberately.
- Local development against an unreleased corpus version needs an editable install or a
  branch pin, which is friction every time.
- A cross-cutting decision now requires knowing the placement rule to find it. The index
  mitigates this; it does not remove it.
- ADRs moving between repositories mid-life is unusual and needs the pointer stubs to be
  disciplined, or links rot.

### Neutral

- The corpus package's name is a branding choice (ADR-009 D1 proposes `wegofwd-arivu`); the
  topology does not depend on it.
- Whether family-level ADRs eventually consolidate into `wegofwd-llm/docs` can be decided
  when there is more than one of them.

## Alternatives considered

- **Everything in `kathai-chithiram`, corpus as a subfolder.** Rejected — Decision 2. The
  deciding cost is the privacy and legal posture, not the build.
- **Start in `kathai-chithiram` and extract the corpus when it hurts.** Considered seriously
  and rejected. The extraction cost here is not paid in code, so "when it hurts" never
  arrives — the muddied data claim does not produce a symptom a developer feels, only an
  awkward answer to a question asked much later.
- **A true monorepo with workspace tooling.** Rejected as over-built for a solo project with
  three packages and no shared build complexity. Revisit if the family grows substantially.
- **Separate repositories for all three now, including the assistant.** Rejected —
  Decision 3. Creating the assistant repository contradicts ADR-009 D5's sequencing and
  invites work that should wait.
- **Per-repository ADR numbering.** Rejected — Decision 6. Two `ADR-001`s would make every
  cross-reference in every document ambiguous.

## Migration / rollout

- **Not yet started.** Proposed; nothing has moved.
- **Ratification condition (Proposed → Accepted):** the corpus repository created under
  `KC-18`, consumed by `kathai-chithiram` as a pinned dependency in the established pattern,
  with `ADR-010`/`ADR-011` moved and pointer stubs left behind.
- **Order:** `KC-18` creates the repo → the ADR move lands in the same change → the corpus is
  added to `docs/shared-services.md` as a third family member → `KC-21` makes
  `kathai-chithiram` its first consumer.
- **Docs:** `docs/ADR_INDEX.md` (created now, so the family has one findable list from the
  start); `docs/shared-services.md` (add the package when it exists).
- **Explicitly not doing now:** creating the assistant repository, moving any ADR, or adding
  monorepo tooling.
