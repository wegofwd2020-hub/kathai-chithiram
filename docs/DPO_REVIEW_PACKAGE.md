# DPO / counsel review package — Kathai Chithiram

**Status:** Prepared for review (2026-07-02) · **Owner:** WeGoFwd2020
**Prepared by:** engineering, for a Data Protection Officer / qualified data-protection counsel.

> **One entry point for the data-protection review.** This collates everything a
> reviewer needs to assess Kathai Chithiram's processing of special-category child
> data and to sign off (or gate) an EU/UK launch. It **prepares for** legal review —
> it does **not** substitute for it, and nothing here is legal advice or a sign-off.
> The authoritative assessment is `docs/DPIA.md`; this package points at it and the
> surrounding evidence, and names the specific decisions we need from you.

## How to use this package

Suggested reading order:

1. **This page** — scope, what's enclosed, and the exact asks (10 min).
2. **`docs/DPIA.md`** — the assessment itself: Art. 35 triggers, processing
   description, necessity/proportionality, the R1–R10 risk register with residuals,
   and §5 launch preconditions. *This is the document to sign off.*
3. **`docs/PARENT_PRIVACY_NOTICE.md`** — the plain-language notice shown to parents
   at consent. *Review for adequacy/clarity alongside the DPIA.*
4. **`PRIVACY.md`** — the full internal policy the notice derives from (source of
   truth if the two ever differ).
5. **Supporting evidence** (below) — only as needed to verify a specific control.

## What is enclosed

| # | Document | What it is | Why it's in scope |
|---|---|---|---|
| 1 | `docs/DPIA.md` | The DPIA (Draft v0.1) | The assessment under review; carries the risk register + preconditions |
| 2 | `docs/PARENT_PRIVACY_NOTICE.md` | Parent-facing privacy notice (v2026-07-01) | The Art. 13/14 transparency artifact shown at consent |
| 3 | `PRIVACY.md` | Internal privacy & data-handling policy | Source of truth behind the notice; §9 lists open items |
| 4 | `docs/CONTENT_SAFETY.md` | Content-safety rules for generated output | Evidence for R6 (unsafe output) and framing constraints |
| 5 | `docs/R10_DEPLOYMENT_BOUNDARY.md` | Deployment-boundary spec for operator access | Evidence + acceptance criteria for R10 residual |
| 6 | `docs/ADR_001…004_*.md` | Architecture Decision Records | The reasoned basis for the safety (001), profiling (002/003), and access-control (004) stances |
| 7 | `TICKETS/KC-*.md` | Production-hardening tickets | Per-control implementation status cited in the DPIA |

Each DPIA mitigation cites the module or ticket that implements it and states
honestly whether it is **built** or **open**, so a claim can be traced to code.

## The processing, at a glance

*(Full detail in DPIA §2–3; summarized here so a reviewer can orient quickly.)*

- **Purpose (single):** turn one parent's written story about their child into a
  short, calm, captioned animation the child can follow. No secondary use — no
  advertising, no marketing profiling, no third-party sharing.
- **Data subjects:** a child (via their parent/guardian) and the submitting
  parent/guardian.
- **Special-category & children's data:** the story is free text about a child,
  often a child with a disability, and may reveal health/needs data (Art. 9). The
  data subject is a child. Both raise the bar.
- **Data collected (minimized):** the story text and the child's **first name only**;
  surname, DOB, address, school, diagnosis, biometrics, and photos are explicitly
  out of scope, with an advisory nudge against over-sharing at intake.
- **Lawful basis:** parent/guardian consent — Art. 6(1)(a), and Art. 9(2)(a)
  explicit consent for special-category content — captured at intake and tied to the
  specific privacy-notice version shown.
- **Provider processing:** generation runs through a provider-agnostic seam; the
  child's name is stripped before any provider call and reinserted only at render;
  the provider must be configured no-training / zero-retention.
- **Retention & erasure:** undelivered content deleted within 30 days; verifiable
  hard-delete on request, cascading to backups; per-story crypto-shredding (KC-10).

## Risk posture summary (from DPIA §4)

Nine of ten risks sit at **Low** residual with the control **built**. Two remain
above Low and are the reviewer's focus:

- **R8 — profiling of a child (Medium residual).** Only fixed primitives are
  captured (prompt level, completion, 1–5 mood), no free text, keyed to opaque ids,
  under the same retention + hard-delete. The engine that would *act* on that data is
  **gated off** (ADR-002/003 ship no thresholds and cannot run until a clinician
  supplies a policy). Residual stays Medium until the profiling touchpoint (below) is
  reviewed.
- **R10 — operator browses content (Medium residual).** Deny-by-default access
  control is built and wired into every app flow with a log-safe audit trail
  (ADR-004). Residual stays Medium on a single machine because an operator can bypass
  the app via direct filesystem access; the deployment boundary that drops it to Low
  is specified in `docs/R10_DEPLOYMENT_BOUNDARY.md`.

## What we are asking you to decide

Mapped to DPIA §5 (launch preconditions) and §6 (sign-off). We need your judgment on:

1. **Sign-off (or gating) of the DPIA and the parent notice** — the core ask
   (DPIA §5.1, §6). Are the assessment, the residuals, and the notice adequate for
   the intended launch, and what conditions attach?
2. **Adequacy of the lawful basis** — parent/guardian consent under Art. 6(1)(a) +
   Art. 9(2)(a), including how guardianship is evidenced and consent withdrawn.
3. **Automated decision-making (Art. 22)** — confirm the *suggest-only, therapist-
   decides, human-review-before-delivery* design keeps the (gated) progress engine
   clear of Art. 22 solely-automated decisions with legal/significant effect.
4. **The R8 progress-profiling touchpoint** (DPIA §5.5) — what you need before the
   engine could be enabled, to be completed with the professional collaborator.
5. **The R10 deployment boundary** — whether the acceptance criteria in
   `docs/R10_DEPLOYMENT_BOUNDARY.md` §5 are sufficient to reassess R10 → Low.

## Gaps we want your eyes on (not yet resolved in the DPIA)

We are surfacing these honestly rather than assuming them closed:

- **International transfer.** The LLM provider may process story text outside the
  UK/EU. The DPIA does not yet specify a transfer mechanism (adequacy / SCCs / UK
  IDTA) or a transfer risk assessment. *We need direction on what is required.*
- **Controller/processor roles & DPA.** WeGoFwd2020 as controller; the LLM provider
  and any hosting as processors/sub-processors — the DPA / sub-processor terms and
  the no-training/ZDR posture need to be evidenced contractually (R2 is currently an
  *operational* assumption the code cannot verify).
- **Data-subject rights beyond erasure.** Hard-delete covers erasure; access,
  rectification, and objection request handling (and the response SLA) are not yet
  documented as a process.
- **Retention justification.** The 30-day undelivered-content default is implemented
  but not yet justified/documented against necessity.
- **Breach & DPO contact.** Breach-notification process and the DPO point of contact
  are not yet recorded in the DPIA.
- **Accounts.** If/when accounts exist, the minimal account/contact data (DPIA §2
  table) needs its own basis and retention.

## Current posture (what is and isn't live)

- **Prototype.** No EU/UK launch and no multi-user/networked deployment is cleared
  by this package. The human-review gate before any output reaches a child is
  **mandatory** and remains on (CLAUDE.md; DPIA §5).
- **No real child data** beyond what a consenting parent submits for their own child;
  tests and fixtures use synthetic data only.
- Acceptance of ADR-004 records that access control is *built*, not that networked
  enforcement is in place — see that ADR's acceptance note.

## Sign-off record

| Role | Name | Decision | Conditions | Date |
|---|---|---|---|---|
| Owner | WeGoFwd2020 | Package prepared | — | 2026-07-02 |
| DPO / counsel | _pending_ | _pending_ | _pending_ | — |
| Professional collaborator (if engine in scope) | _pending_ | _pending_ | _pending_ | — |

Return path: annotate this table (or reply against the numbered asks above) with
your decision and any conditions. Conditions feed back into DPIA §5 as gating
preconditions before launch.

---

*This package is reviewed and re-issued whenever the DPIA, the data flow, the
provider configuration, or the set of collected data changes (DPIA review cadence:
quarterly and before any launch).*
