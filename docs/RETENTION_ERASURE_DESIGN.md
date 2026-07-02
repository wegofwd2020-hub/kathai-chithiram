# Retention & erasure design — accounts, families, children, programs, DOB

**Status:** Design v0.1 (2026-07-02) · **Owner:** WeGoFwd2020 · **Scope:** the
**proposed, not-yet-built** multi-user entities in ADR-005 parts b/c.

> This is a **design note**, not code and not a policy sign-off. It satisfies precondition
> **A6.3** of `docs/DPIA_ADDENDUM_accounts_and_dob.md` ("retention + erasure design for the
> new entities, with a cascade-delete test") so the accounts/DOB expansion is decision-ready.
> The **retention periods and the erasure-vs-clinical-retention conflict (§6, §7) are
> DPO/counsel decisions**; this note proposes the mechanism and surfaces those choices. No
> code ships until the ADR-005 D7 / addendum A6 gate clears.

---

## 1. What exists to build on

- **KC-1 verifiable hard-delete** (`storage/deletion.py::delete_story`): `rmtree` the
  story dir, **assert no artifact remains**, write a `DeletionReceipt`, and append the id
  to an append-only **`BackupPurgeLog`** the backup job consumes next cycle.
- **KC-10 crypto-shredding**: each story is encrypted under its own random data key,
  stored only *wrapped* by the master; deleting the story destroys the wrapped key, so its
  content is unrecoverable **even from a stale ciphertext backup**, without waiting on the
  backup layer.
- **30-day retention sweep** (`storage/retention.py`): undelivered story text is purged
  after 30 days unless the parent saved it.

The new model must extend these three — verifiability, crypto-shred, and a retention
sweep — from a **flat set of stories** to a **family → child → {stories, program,
progress, DOB}** graph plus **accounts**.

## 2. Target properties

A correct implementation must guarantee:

1. **Cascading** — erasing a node erases everything below it; **no orphans** (a deleted
   child leaves no story/program/progress/DOB anywhere).
2. **Verifiable** — after erasure, a walk of the subtree asserts no artifact remains (KC-1
   extended to the graph), and the backup-purge log carries every removed id.
3. **Crypto-shred first** — destroying a node's key renders its content unrecoverable in
   one step, before and independent of `rmtree`/backup cycles (KC-10 extended to a key
   *tree*).
4. **Per-subject** — each data subject can exercise erasure over the data they own or that
   is about them (§5), and only that.
5. **DOB is treated as child-identifying** — it lives on the child record under the
   child's key and is shredded with the child.

## 3. Proposed entity + key model

Content is **family-owned**; parents are *members*; a therapist is *assigned*, never an
owner. A proposed key tree makes crypto-shred cascade for free:

```
master key (KC_STORAGE_KEY, in a secret manager)
└─ per-family key            (wraps family record)
   └─ per-child key          (wraps child record incl. DOB, program, progress)
      └─ per-story key        (KC-10, wraps that story's artifacts)
```

Each key is stored only *wrapped by its parent*. **Destroying a node's wrapped key
crypto-shreds that node and everything beneath it in one operation** — deleting a child
destroys the per-child key, so its DOB, program, progress, and every story under it are
immediately undecryptable, even if raw ciphertext lingers in a backup. Account credentials
are stored separately (never wrapped by content keys) so an account can be closed without
touching content, and vice-versa.

## 4. Erasure cascade rules (proposed)

| Erase | Effect | Notes |
|---|---|---|
| **One story** | KC-1 delete_story unchanged (shred per-story key, rmtree, verify, backup-log). | Already built. |
| **A child** | Shred the **per-child key** → DOB + program + progress + all the child's stories unrecoverable at once; then rmtree the child subtree, assert empty, backup-log the child id + each story id. | The core new cascade. |
| **A family** | Shred the **per-family key**, cascade-erase every child (above), remove the family record and all parent memberships. | Whole-family erasure. |
| **A parent account — family has other parents** | Remove that parent's membership + personal account data; **children's content stays** (family-owned). | Avoids orphaning a child's data when one of two parents leaves. |
| **A parent account — last parent** | Treated as **family erasure** (no owner would remain). | Or block until another owner is named — a **DPO/product choice** (§7). |
| **A therapist account** | **Unassign** from every child/program + remove the therapist's personal account data. Family content is untouched (they never owned it). | If the therapist's org is a *separate controller* (addendum A4.3), their own retained copy is **out of our erasure scope** — a DPA/clinical-retention matter (§7). |

## 5. Who may erase what (DSAR mapping, proposed)

- **Parent (family member)** — may erase the whole family, any of its children, any story,
  and their own account. This is the child's erasure right, exercised by the guardian.
- **Therapist** — may erase **their own account** (→ unassignment). May **not** erase a
  family's content (not the owner); a therapist-initiated deletion of clinical records they
  control is governed by their org's duties, not this system.
- **Operator / support** — may action a verified erasure request on a subject's behalf,
  through the same guarded, audited path (ADR-004) — every erasure is authorized and
  logged like every other access.

Access, rectification, and objection (the DSARs beyond erasure the DPO package still flags
as open) reuse the same guarded read/update paths; this note covers **erasure**.

## 6. Retention rules (proposed defaults — **DPO to confirm**)

| Data | Proposed retention | Basis / note |
|---|---|---|
| Undelivered story text | 30 days (unchanged) | Existing KC-1 sweep. |
| Delivered story + scene script + media | Life of the family relationship, then on erasure | Kept so a child can re-watch; purged on account/child/family erasure. |
| Child record + **DOB** | Life of the child's participation; purged on child/family erasure | Minimized to the child (ADR-005 D4); **granularity — full DOB vs age band — is the open A3 decision**. |
| Program + per-child progress | Life of the program, then on erasure | Reinforces R8/R14; framing stays non-clinical. |
| Account (parent/therapist) | Until closed + a short grace (e.g. 30 days), then purged | Grace covers accidental closure; **grace length is a DPO/product choice**. |
| Audit log (ADR-004) | A defined period, log-safe (opaque ids only) | Security/accountability need vs minimization — **DPO to set the period**. |

**⚠ The one real conflict (§7):** if a therapist/clinic is a *controller* of a child's
clinical program, **statutory clinical-record retention** may *require* keeping records the
parent asks to erase (Art. 17(3)(b) — retention for a legal obligation can override erasure).
This system cannot resolve that; it must be decided per the controller/processor split.

## 7. Open questions for DPO / counsel

- The retention periods in §6 (delivered content, DOB, program/progress, account grace,
  audit-log period) — confirm or set.
- **Erasure vs clinical-record retention** — when a therapist's org is a controller, which
  wins, and what does *our* erasure then guarantee (erase our copy; the org retains theirs
  under its own duty)?
- **Last-parent deletion** — cascade-erase the family, or block until another owner is
  named?
- **Backups** — the addendum assumes crypto-shred makes stale ciphertext safe; confirm this
  satisfies the erasure obligation for the backup layer, or whether an active backup purge
  is also required.
- **DOB granularity** (A3) directly changes what "erase the DOB" removes.

## 8. Verifiability & the cascade-delete test (build precondition)

When (b)/(c) are built, the erasure implementation must ship with a test that, for a family
with ≥2 children each with ≥1 story + program + progress + DOB:

1. Records the per-family/child/story key material and every artifact path.
2. Erases the family.
3. Asserts **(a)** every key is destroyed (no wrapped copy survives), **(b)** a walk of the
   store finds **no artifact** of any child/story/program/DOB (KC-1's "assert nothing
   remains", graph-wide), **(c)** holding the master key + a captured pre-deletion backup
   ciphertext, decryption **fails closed** (crypto-shred proven, as KC-10's test does), and
   **(d)** the backup-purge log contains the family + every child/story id.

This is the same standard KC-1/KC-10 already meet per story, lifted to the graph. **No
erasure code ships before the ADR-005 D7 / addendum A6 gate clears.**
