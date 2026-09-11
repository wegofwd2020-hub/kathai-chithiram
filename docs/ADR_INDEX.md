# Kathai Chithiram — ADR index

**As of:** 2026-09-10 · One findable list of every architecture decision in the family.

> An **ADR** (Architecture Decision Record) captures one significant decision: the situation
> that forced it, what was decided, what it costs, and what was rejected. It is written once
> and not rewritten — if a decision changes, a *new* ADR supersedes the old one, so the
> reasoning stays readable years later.
>
> ADR numbers are unique across the whole `wegofwd` family, not per repository, so
> "ADR-011" means one thing regardless of where the file currently lives (ADR-012 D6).
>
> **Status vocabulary:** *Proposed* = decided in writing, not yet built. *Accepted* = the
> design is realised in code. Acceptance says the mechanism exists — it does **not** mean a
> capability is switched on. Several accepted ADRs describe things deliberately built and
> left inert behind a named gate.

---

## At a glance

| # | Decision | Status | Home |
|---|---|---|---|
| 001 | Child-perspective capture: instructional only; experiential deferred entirely | Proposed (2026-06-13) | kathai-chithiram |
| 002 | Progress quantification: capture now, suggest only, engine gated | **Accepted** (2026-06-30) | kathai-chithiram |
| 003 | Progress engine: deterministic, and every clinical value comes from a policy file | **Accepted** (2026-07-01) | kathai-chithiram |
| 004 | Operator access control: deny by default at the storage boundary | **Accepted** (2026-07-01) | kathai-chithiram |
| 005 | Multi-user platform: sequenced by data risk, accounts gated | Proposed (2026-07-02) | kathai-chithiram |
| 006 | Domain model: capability layers before weights, on a permissive small base | Proposed (2026-09-10) | kathai-chithiram |
| 007 | Scene-script v2: a closed art vocabulary and a checkable authoring grammar | Proposed (2026-09-10) | kathai-chithiram |
| 008 | Training corpus: wholly synthetic, clinician-adjudicated, provenance-carrying | Proposed (2026-09-10) | kathai-chithiram |
| 009 | The context dictionary: one knowledge asset, two surfaces — educate/never-advise; broad-vision / narrow-start scope | Proposed (2026-09-10, rev. 2026-09-11) | kathai-chithiram |
| 010 | Retrieval-first: facts live in the corpus, never in the weights | Proposed (2026-09-10) | `wegofwd-arivu` (moved) |
| 011 | Corpus rights and freshness: what may be ingested, and how it stays true | Proposed (2026-09-10) | `wegofwd-arivu` (moved) |
| 012 | Repository topology: where everything lives as the family grows | Proposed (2026-09-10) | kathai-chithiram |
| 013 | The practice-assistant surface and its commercial model — two layers, money never bends the answer | Proposed (2026-09-11) | kathai-chithiram |

001–005 predate this round of work. 006–012 were written in September 2026 and **none of
them has been built**.

---

## The through-line

Read as a set, eleven of these twelve are variations on one principle:

> **Where a decision affects a child, the machine carries out a rule that a person authored,
> and the person can always see and change the rule.**

ADR-003 says it most sharply — there is no `DEFAULT_K` and no fallback threshold anywhere in
the progress package, "so an engineer's cutoff cannot reach a child by omission." ADR-007
applies the identical rule to how much a story should tell a child what to do. ADR-010
applies it to knowledge: a claim the reader cannot trace to a source is not made at all.
ADR-001 states the limit: "automation is never the sole safeguard."

The twelfth (ADR-012) is plumbing.

---

## The decisions in full

### ADR-001 — Child-perspective safeguarding *(Proposed)*
**Decided:** A story has three independent attributes — who wrote it, whose voice it is in,
and whether it teaches or reflects. Ship the teaching kind only. **Do not build** anything
that captures a child's own account of a distressing experience.

**Why it matters:** This is the ADR that says no to the most emotionally appealing feature in
the space. Capturing a child's own voice sounds like respect; done without a safeguarding
protocol it is a disclosure surface with no plan for what arrives on it. It sets six hard
preconditions before that work may even begin — including a written risk-of-harm protocol
co-designed with a qualified professional and reviewed by counsel, an explicit
confidentiality model, and a rule that a child's distressing account is never automatically
played back to them.

**The line everything else inherits:** *automation is never the sole safeguard.*

---

### ADR-002 — Progress quantification *(Accepted)*
**Decided:** Record a fixed, minimal set of session facts — was the child refused, prompted,
or independent; did they complete it; a brief mood check-in. Compute nothing yet. When
computation is switched on it may only *suggest* a change to a therapist, never make one.

**Why it matters:** It draws the line between measurement and judgement, and it deliberately
refuses a free-text clinical-notes field — because a free-text box invites the recording of
things the system has no lawful basis or safeguard to hold. It also names the data honestly:
this *is* profiling of a child, and it carries the strictest privacy treatment in the system.

**Still switched off.** Six preconditions remain, four of them not engineering work.

---

### ADR-003 — Progress engine design *(Accepted)*
**Decided:** The engine is two pure functions — measure, then suggest — with no clock, no
randomness, no network and no model. **Every clinical number lives in a policy file supplied
as configuration.** Engineering ships the interpreter and never the values.

**Why it matters:** This is the pattern the rest of the system copies. How many sessions
count as evidence, what counts as progress, what wording a suggestion uses — all of it is
authored by a clinician in a reviewable file, not chosen by a developer. "Not enough data"
and "no clear signal" are proper answers, not errors. The indicator carries its own evidence,
so a therapist can always see exactly what produced a verdict.

---

### ADR-004 — Operator access control *(Accepted)*
**Decided:** Every access to a family's content requires an identified caller with an
explicit relationship to that story. No relationship means nothing is returned, and the
attempt is logged.

**Why it matters:** Encryption protects a stolen laptop; it does nothing about a person with
legitimate system access browsing a child's story out of curiosity. This closes that
separately. Three roles — family owner, reviewer, therapist — each get exactly what they
need and no more. Every access, allowed or denied, leaves an audit record containing no
names and no story text.

---

### ADR-005 — Multi-user program platform *(Proposed)*
**Decided:** Move from a single-operator tool to a real platform with families, children and
therapists — but sequence it by data risk. The guided story template adds no personal data
and is built. Accounts and a child's date of birth expand what the system holds, and are
gated on a privacy-impact revision.

**Why it matters:** It is the decision to grow carefully rather than build the obvious
account system first. It also takes a minimisation stance up front: collect the child's age
information only, never the parents'.

---

### ADR-006 — Domain model strategy *(Proposed)*
**Decided:** Do not build a language model from scratch. Break "understands special-needs
story authoring" into five capabilities and notice that only one lives in the model:
producing valid structured output is a decoding constraint, choosing drawable artwork is a
contract problem, narrative grammar is mostly automated checks, and recognising risk of harm
is deliberately *not* the model's job. Only situational judgement is learned. Adapt a small,
permissively licensed model for that one thing.

**Why it matters:** It reorders the work so that most of the quality gain arrives before any
model training, and it changes what the system can promise about privacy — a model running
on our own hardware means a child's story is never sent to another company at all.

**Restated prohibitions:** never train on a real child's story; never let a child's recorded
mood become something the model is optimised to raise; never relax the human review gate
because the model got better.

---

### ADR-007 — Scene-script v2 *(Proposed)*
**Decided:** Write down the complete list of things the animation can actually draw, and
make asking for anything else an error. Add the story's voice and purpose to the contract.
Label what each scene is *doing* — describing, naming a feeling, coaching, or reassuring —
so the balance between them can be checked automatically against a clinician-set ratio.

**Why it matters:** Today a story can ask for a supermarket, pass every check, and reach the
child as a figure standing in a blank room — and nothing reports it. The drawable vocabulary
is six backgrounds, four expressions, two gestures and about nineteen objects, and it is
written down nowhere the system can see it. This is the single largest quality problem in
the product and it needs no AI to fix.

**Also decided:** use "social narrative" rather than "Social Stories™", which is a registered
trademark for a specific methodology with its own training.

---

### ADR-008 — Training corpus provenance *(Proposed)*
**Decided:** If a model is ever trained, it learns from wholly invented material — situations
and child profiles designed with a clinician — never from a real family's submission, in any
form. Every example records where it came from and who approved it.

**Why it matters:** A model does not forget when a family asks to be deleted. That single
fact rules out the obvious training data permanently. Building from nothing turns out to be
the advantage: a wholly synthetic corpus is the only kind whose origins can be described
completely.

**The honest weakness recorded in it:** invented parent voices are tidier than real ones, and
a model trained on tidy inputs may fail on a real message written at 3 a.m.

---

### ADR-009 — The context dictionary: one knowledge asset, two surfaces *(Proposed)*
**Decided:** The story generator is a *surface* on an asset that does not exist yet — a
curated, citable body of practice knowledge. Build the asset. Four audiences, served in
order: parents (today), helper-learners, lifespan navigators, and builders (a by-product,
never a product).

**Primary goal + scope (rev. 2026-09-11):** the asset's name is the **"context dictionary"**
and it is the product's *primary goal* — the animation and the assistant are surfaces of it
(Decision 8). Scope is **broad by vision** (disability + aging + accessibility across life
contexts) but **incremental by domain**: start in special-needs practice, add aging, then
built-environment / housing accessibility, each with its own rights check (Decision 9). This
reframes the *why*, not the build order (Decision 5) or the educate-cite-never-advise law
(Decision 3).

**The product law:** *educate, always cite, never advise.* No recommendation about a specific
person, no eligibility decisions, no assessment or diagnosis. An answer with no source is not
produced.

**Why it matters:** It keeps the work coherent instead of scattered, and keeps the product
outside clinical-decision-support regulation on the merits rather than behind a disclaimer.
It also says the assistant holds **no personal data at all** and must decline any question
describing a specific real person.

**And it makes the risk-of-harm path a precondition.** A volunteer will ask "what do I do when
he hits himself." That is not a corpus question. Nothing ships until there is a real answer.

---

### ADR-010 — Retrieval-first *(Proposed)*
**Decided:** Facts live in the corpus, never in the model's weights. The model reads
retrieved passages and writes a plain answer over them. Nothing more.

**Why it matters:** Every claim must be checkable, updatable, retractable and attributable.
Weights give none of those: you cannot cite them, you cannot correct them when a state
changes a rule, you cannot withdraw a claim when guidance is rescinded. "I don't have a
source for that" becomes a correct answer rather than a failure.

**This deliberately reverses ADR-006 for this track** — and the reason is in ADR-006's own
breakdown. The story generator's hard problem is judgement; the assistant's hard problem is
truth.

---

### ADR-011 — Corpus rights and freshness *(Proposed)*
**Decided:** Three tiers of source with a prohibition list. Every source carries its licence
terms recorded word for word, and nothing is ingested without one. Attribution appears with
the answer, not on a credits page.

**Why it matters:** Two traps decide most cases. *Free to read is not licensed for reuse* —
several of the best-known sources in the field permit neither. And *federally funded is not
federally authored* — a university grantee keeps its copyright, which is why the single most
useful practice material in the field is the one we may not take.

**And freshness here is not staleness.** Withdrawn guidance and retired clinical reports read
as authoritative while being wrong, so the corpus tracks supersession and retraction as
first-class facts.

**Never:** content scraped from parent forums or social media — health information about
identifiable people, often children, who never consented.

---

### ADR-012 — Repository topology *(Proposed)*
**Decided:** The corpus gets its own repository from the start. The assistant gets one later
and is not created yet. ADRs live with the code they govern; a scope decision lives where the
scope changed.

**Why it matters:** The deciding argument is not code tidiness. The corpus must be able to
demonstrate it holds no personal data, and that claim is muddied by living inside a
repository whose every policy document is about one child's sensitive data.

---

### ADR-013 — The practice-assistant surface and its commercial model *(Proposed)*
**Decided:** The commercial idea (surface "products available for sale" alongside answers,
Google/Amazon-style) is allowed only under strict separation. Commerce lives **only on the
practice-assistant surface**, never on the child animation. Two visibly separate layers: (A)
the cited educational answer, and (B) a labelled, disclosed "products that address this"
section — and **money never bends Layer A**. Categories and disclosed listings, not
individualised purchase advice. Regulated/medical-device/health-claim products are gated
pending counsel.

**The clinician distinction:** clinicians and therapists **inform the corpus** (what the
dictionary knows); the surface still **educates, cites and routes to a human** — it does not
give live advice. Monetisation touches Layer B only.

**Why it matters:** it is the commercial analogue of ADR-009 D3 (educate/cite/never advise) —
the rule that keeps the product outside clinical-decision-support regulation and trustworthy
to a vulnerable audience. It fixes the boundaries so "should we monetise?" stays an open,
deliberate choice rather than one foreclosed by a leaky design.

**Still the owner's call (open):** revenue mechanism (affiliate / sponsored / marketplace),
v1-or-later timing, commerce vs subscription/grant (a values call), and launch categories.
**Counsel-gated** before ratification (FTC disclosure, advertising to vulnerable populations,
device/health-claim promotion). Downstream of Kathai Chithiram shipping and the risk-of-harm
path — not a now-build.

---

## Which decisions are waiting on a person

Not on engineering. These are the real blockers.

| Waiting on | Blocks |
|---|---|
| **A named professional collaborator** | ADR-002's remaining preconditions (the progress engine stays off), ADR-007's narrative ratio policy, ADR-008's entire corpus, ADR-009's risk-of-harm path |
| **A data-protection / legal review** | ADR-005's accounts and date-of-birth work, ADR-011's source tiering, ADR-013's commercial-model review (FTC disclosure, advertising to vulnerable populations, device/health-claim promotion) |
| **A deployment boundary** | The last step of ADR-004; the residual risk stays medium until operators cannot reach the files directly |

Everything else is buildable now.
