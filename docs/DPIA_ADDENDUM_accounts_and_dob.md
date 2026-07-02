# DPIA Addendum — accounts, families, and child date of birth (ADR-005 parts b/c)

**Status:** Draft v0.1 (2026-07-02) · **Owner:** WeGoFwd2020 · **Assesses:** the
**proposed, not-yet-built** multi-user expansion in
`docs/ADR_005_multi_user_program_platform.md` (parts b + c).

> This addendum extends `docs/DPIA.md`. Like it, it is an **internal assessment for
> alignment**, **not legal advice**, and **not a sign-off** — it must be reviewed by a
> Data Protection Officer / qualified counsel. It exists to make the accounts + DOB
> expansion a *decision-ready* item: it describes the new processing, the new risks, and
> the specific decisions we need from a DPO **before any of this is built**. Nothing here
> is implemented; ADR-005 Decision 7 gates the code on this review. Once (b)/(c) are built
> **and** cleared, this addendum folds into the main DPIA and the R-register renumbers.

---

## A1. What changes, and why a fresh assessment

The current DPIA (v0.1) assesses a **single-operator** tool that collects **only the
story and the child's first name**, and lists **surname, DOB, address, school, diagnosis,
biometrics, photos, and accounts as explicitly out of scope** (DPIA §3, PRIVACY §3). That
is a deliberate minimization posture.

ADR-005 (b)/(c) **changes the data model**:

- **User accounts** — parents and therapists become authenticated account holders, with
  contact/identity data and credentials.
- **A family / child / therapist graph** — content is scoped to a family and its children;
  a therapist is *assigned* to a child/program; a family may have multiple children.
- **Child date of birth** — captured to build **age-aware progress patterns**.
- **Programs + progress reporting** — a therapist establishes a program for a child; the
  M1 progress records (already assessed as R8) aggregate **per child across stories**, and
  are **reported back to parents**.

Each of these adds personal data and/or a new relationship the current DPIA does not
cover, so a fresh assessment is required **before** implementation (Art. 35(11): keep the
DPIA under review; a material change to processing re-triggers it).

## A2. New / changed data (extends DPIA §2 table)

| Data | Category | Sensitivity | New? |
|---|---|---|---|
| Parent account: name, email/contact, credentials | Personal identifier + authentication | Medium | New |
| Therapist account: name, professional identity, credentials | Personal identifier + authentication | Medium | New |
| Family ↔ parent ↔ child ↔ therapist relationships | Personal (association / who-treats-whom) | High | New |
| **Child date of birth** | Personal identifier; **reveals age of a vulnerable child** | **High** | New |
| Program definition (goals, content plan) for a child | Derived; about a child's needs (may imply Art. 9) | High | New |
| Progress records aggregated **per child** (from R8 feedback) | **Profiling** of a child | High | Reinforced |
| Parent-facing progress report | Derived profiling, shown to the family | High | New |

**Data subjects gained:** the **parent** and **therapist** as account holders (their own
identity data), in addition to the child. The child's DOB makes the child directly
identifiable in a new way.

## A3. Necessity & proportionality (extends DPIA §3)

- **DOB — minimize hard (Art. 5(1)(c)).** ADR-005 D4 already drops parent/therapist DOB
  as unnecessary — **only the child's DOB** serves the age-norming purpose. **Open decision
  for the DPO:** does age-norming need *full* DOB, or does a **birth month-year / age
  band** suffice? Prefer the least-granular form that serves the purpose; full DOB should
  be justified or downgraded.
- **Accounts — collect the minimum to authenticate + contact.** No demographic data beyond
  what identity + delivery require; no marketing profile.
- **Purpose limitation.** Accounts, DOB, and programs are used only to run and report a
  child's program — never advertising, never third-party sharing.
- **Storage limitation.** Account/family/child/program/progress records need their own
  retention rule and an erasure path (A5 R15), distinct from the 30-day undelivered-content
  sweep.

## A4. Lawful basis & controller/processor (extends DPIA §3, §6)

Decisions needed from the DPO/counsel:

1. **Basis for the child's data (incl. DOB + progress).** Continue on **parent/guardian
   consent** (Art. 6(1)(a) + Art. 9(2)(a)); confirm how guardianship is evidenced when an
   account, not a one-off intake, holds the relationship, and how consent is withdrawn per
   child.
2. **Basis for account data (parent/therapist).** Likely **contract / legitimate interests**
   for running the service vs. consent — the DPO should set this; it differs from the
   child-content basis.
3. **Controller / processor roles.** If a therapist belongs to an external clinic/org, is
   that org a **controller** (or joint controller) for the child's clinical program? A
   **DPA** between WeGoFwd2020 and the therapist's org is likely required (this is already
   an open gap in `docs/DPO_REVIEW_PACKAGE.md`).
4. **Children's Code / Age Appropriate Design Code.** Once this is a **multi-user online
   service** processing children's data, the ICO Children's Code (and equivalent regimes)
   likely applies — age-appropriate defaults, DPIA expectations, data minimization for
   children. **Flag for the DPO to confirm scope and obligations.**

## A5. New risks (continues DPIA §4; R11–R15)

Ratings are pre-mitigation inherent, then residual after the (proposed) control.

| # | Risk | Inherent | Proposed mitigation (status) | Residual |
|---|---|---|---|---|
| R11 | **Account compromise** exposes a family's children's content | High | Authentication behind the ADR-004 `IdentityProvider` seam; deny-by-default authz (ADR-004) already gates content; credentials never logged (R9 convention extends). **Seam built; auth deployment + credential storage not built.** | Medium until auth is built + reviewed |
| R12 | **Child DOB** increases re-identification / is over-collected | High | Child-only DOB (ADR-005 D4); least-granular form pending the A3 decision; stored + encrypted at rest (KC-5/KC-10) and swept by erasure (R15). **Minimization decided; granularity open; storage built.** | Low–Medium (depends on A3) |
| R13 | **Therapist over-access** — a therapist assigned to one child sees another family's data | High | Grants lifted from per-story to **child-scoped** (ADR-005 D3); a therapist sees only children they are assigned to; every access audited (ADR-004). **Model decided; child-scoped grants not built.** | Low if built as specified |
| R14 | **Child-level progress profiling** (aggregation + reporting) misused or over-rich | High | Extends R8: fixed primitives only, no free text, non-clinical framing (CONTENT_SAFETY §3/§7); the engine stays gated (ADR-002 D7) and reports are read-only, therapist-decided. **Needs the D7.6 DPIA progress touchpoint + copy review.** | Medium until D7.6 done |
| R15 | **Incomplete erasure** of an account / family / child / program / DOB | High | Erasure must **cascade**: deleting a family/child destroys its stories, programs, progress, DOB, and account records, extending KC-1 hard-delete + KC-10 crypto-shred to the new entities, with a test asserting it. **Not built — a precondition (A6).** | High until built + tested |

Existing risks that shift: **R8** (child profiling) is reinforced by per-child aggregation
and reporting — its residual stays **Medium** and now also depends on R14. **R10** (operator
access) is unchanged but the deployment boundary becomes more important with more subjects.

## A6. Preconditions before building (b)/(c) — the gate (mirrors ADR-005 D7)

All of the following must land **before** any identity/DOB/account/program code:

1. **This addendum reviewed and the A3/A4 decisions made** by DPO/counsel (DOB granularity;
   lawful bases; controller/processor + DPA; Children's Code scope).
2. **Parent notice + consent updated and re-versioned** (KC-8 mechanism) to cover DOB,
   accounts, and program/progress sharing.
3. **Retention + erasure design for the new entities** (R15), with a cascade-delete test —
   the same standard as KC-1/KC-10.
4. **The R8/R14 progress-profiling touchpoint (ADR-002 D7.6)** completed with the
   professional collaborator.
5. **Authentication + credential-storage approach** chosen for the deployment (R11), behind
   the existing seam.

Until all five land, the product stays single-operator (accounts/DOB out of scope), and
`kc author` / `kc generate` / `kc intake` continue to collect only story + first name.

## A7. Consultation & sign-off

This addendum is enclosed with `docs/DPO_REVIEW_PACKAGE.md` (its "accounts,"
"controller/processor," and "retention justification" open gaps are the questions answered
here) and reviewed alongside `docs/DPIA.md`.

| Role | Name | Decision | Conditions | Date |
|---|---|---|---|---|
| Owner | WeGoFwd2020 | Draft prepared for review | — | 2026-07-02 |
| DPO / counsel | _pending_ | _pending_ | _pending_ | — |
| Professional collaborator (progress touchpoint) | _pending_ | _pending_ | _pending_ | — |

*Reviewed whenever ADR-005's model, the data flow, or the set of collected data changes;
folds into `docs/DPIA.md` once (b)/(c) are built and cleared.*
