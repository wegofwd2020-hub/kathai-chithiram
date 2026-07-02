# Data Protection Impact Assessment — Kathai Chithiram

**Status:** Draft v0.1 (2026-07-01) · **Owner:** WeGoFwd2020 · **Review cadence:** quarterly, and before any change to data flow or any launch.

> This DPIA is an internal assessment for alignment and is **not legal advice**
> and **not a sign-off**. It must be reviewed by a Data Protection Officer /
> qualified counsel before any EU/UK launch. It is the source assessment behind
> the PRIVACY.md §8/§9 commitment; where it references a control, it points at
> the module or ticket that implements it, and states honestly whether that
> control is built or still open.

---

## 1. Why a DPIA is required

Kathai Chithiram meets several UK/EU GDPR Art. 35 triggers at once:

- **Special-category data** — a parent's free-text story about their child, often
  a child with a disability; the story may reveal health/needs data (Art. 9).
- **Data concerning children** — the data subject is a child; the processor is
  their parent/guardian.
- **Profiling** — the ADR-002 per-session feedback (prompt level, completion,
  mood) is behavioural data about a child.
- **Innovative technology** — generative AI processes the story text.

Any one of these warrants care; together they make a DPIA effectively mandatory
before an EU/UK launch.

## 2. Description of the processing

**Purpose.** Turn one parent's written story into a short, calm, captioned
animation their child can follow. Single purpose; no secondary use.

**Data flow** (see PRIVACY.md §4):

```
Parent story ──▶ generation (wegofwd-llm) ──▶ scene script ──▶ renderer ──▶ animation
   (input)         (provider call, §6)         (derived)        (local)      (output)
                        │
              name stripped before send,
              reinserted only at render
```

**Data categories** (PRIVACY.md §3):

| Data | Category | Sensitivity |
|---|---|---|
| Parent-authored story text | May include Art. 9 health/needs data | High |
| Child first name / nickname | Personal identifier | High |
| Generated scene script (JSON) | Derived from story (token, not name) | High |
| Rendered animation (mp4) | Deliverable | High |
| Per-session feedback (prompt level, completed, mood), keyed to a goal | **Profiling** of a child (behavioural) | High |
| Minimal account/contact (if accounts exist) | Personal identifier | Medium |

**Data subjects.** Children (via their parent/guardian) and the submitting
parent/guardian.

**Scope & retention.** Data is scoped to the owning family. Undelivered story
content is deleted within 30 days (KC-1 retention sweep); a parent can hard-delete
everything at any time.

## 3. Necessity & proportionality

- **Lawful basis:** Art. 6(1)(a) consent, given by the parent/guardian; for
  special-category content, Art. 9(2)(a) explicit consent. Consent is captured at
  intake and, from KC-8, tied to the specific privacy-notice version shown.
- **Data minimization (Art. 5(1)(c)):** only the story and the child's first name
  are collected; surname, DOB, address, school, diagnosis, biometrics, and
  photos are explicitly out of scope (PRIVACY.md §3). An advisory scan nudges
  parents away from over-sharing (`intake/submission.py`).
- **Purpose limitation:** story content is used only to make that family's
  animation — never advertising, profiling for marketing, or third-party sharing.
- **Storage limitation:** 30-day default deletion of undelivered content;
  verifiable hard-delete on request (KC-1).
- **No training on personal data:** stories are never used to train/fine-tune any
  model; the provider must be configured for no-training / zero-retention.

## 4. Risks to individuals and mitigations

Ratings are pre-mitigation likelihood × severity, then residual after the
mitigation. Mitigations cite the implementing control and its **status**.

| # | Risk | Inherent | Mitigation (status) | Residual |
|---|---|---|---|---|
| R1 | Child's name/identifiers leak to the LLM provider | High | Name stripped + pseudonymized before send; residual match is a hard stop (`IdentifierLeakError`). **Built — KC-2.** | Low |
| R2 | Story text retained or used for training by the provider | High | Provider must be no-training / zero-retention (an org-level configuration of the account the key belongs to); the seam refuses dispatch otherwise and records the posture per request. Backed by a **dedicated, isolated ZDR credential** (`ANTHROPIC_ZDR_API_KEY`) that fails closed if absent — no fallback to a general key. **Built — KC-6.** (Residual assumes the key is provisioned against an org Anthropic has confirmed as no-training / zero-retention — an operational precondition, not something the client can verify.) | Low |
| R3 | Personal story data readable at rest (disk/backup theft) | High | Artifacts encrypted at rest with AES-256-GCM, key supplied from config (`KC_STORAGE_KEY`), distinct from the LLM key; a stolen disk/backup is ciphertext without the key. **Built — KC-5.** Each story is now encrypted under its own random data key, stored only wrapped by the master (envelope encryption); master-key rotation re-wraps the per-story keys **without** re-encrypting artifact bodies, so rotation is incremental and localizes blast radius. **Built — KC-10.** (Residual assumes the master key is stored separately from the data/backups.) | Low |
| R4 | Data kept longer than needed | Medium | 30-day retention sweep of undelivered content; hard-delete on request. **Built — KC-1.** | Low |
| R5 | Incomplete deletion leaves recoverable personal content | High | Verifiable hard-delete asserts no artifact remains; backup-cascade log. **Built — KC-1.** Delete now also destroys the story's wrapped data key, so its artifacts are cryptographically unrecoverable even if raw ciphertext survives in a stale backup (crypto-shredding) — deletion no longer depends on the backup layer dropping every byte. **Built — KC-10.** | Low |
| R6 | Unsafe/inappropriate output reaches a child | High | Content-safety generation rules + scene-script validation + render-time seizure/flash guards + a human-review gate before delivery. **Built — KC-3/KC-4/KC-7.** | Low |
| R7 | Consent not informed / not demonstrable | Medium | Explicit consent captured at intake; parent shown a plain-language notice, and the notice version is recorded against the consent. **Built — KC-8.** | Low |
| R8 | Profiling of a child (feedback) misused or over-collected | High | Fixed primitives only, no free text; keyed to opaque ids; inherits retention + hard-delete; engine that would act on it is gated behind ADR-002 preconditions. **Capture built; engine gated — ADR-002.** | Medium |
| R9 | Sensitive data exposed in application logs | Medium | Errors and logs are constructed to carry no raw story text, captions, or names (lengths/counts only). **Built — errors.py / logging conventions.** | Low |
| R10 | Operator browses story content | Medium | Deny-by-default access control is **built and wired into the app** (ADR-004 / KC-11): a `GuardedStore` authorizes a principal against per-story grants, and the CLI/intake/review flows now run through it. Residual stays Medium: on the single-machine prototype an operator retains direct filesystem access to the store (bounded only by KC-5 encryption + OS perms), so in-app enforcement drops the residual to Low only under a deployment boundary that removes that bypass. Every allowed/denied access is now persisted to a log-safe audit trail. | Medium |

## 5. Residual risk and launch preconditions

The two highest-inherent-risk controls are now built in code: at-rest encryption
(R3, KC-5) and the dedicated ZDR / no-training credential (R2, KC-6). What
remains before an EU/UK launch is **operational and human**, not unwritten code.
**This DPIA cannot be signed off until, at minimum:**

1. A **DPO/counsel review** of this document and the parent-facing notice.
2. **R2 operational precondition:** `ANTHROPIC_ZDR_API_KEY` is provisioned
   against an Anthropic organization **confirmed** to be no-training /
   zero-retention (the code fails closed without the key, but cannot itself
   verify the org's posture).
3. **R3 key management:** `KC_STORAGE_KEY` is stored in a secret manager separate
   from the data/backups, with a documented rotation plan. (Per-story envelope keys
   for crypto-shredding on delete and incremental master-key rotation are now built
   — **KC-10**; provisioning the secret manager itself remains operational.)
4. R10 access-control enforcement is decided (technical control vs. documented
   operational limit) for the intended deployment — tracked as **KC-11**.
5. If the ADR-002 progress **engine** is enabled, its own DPIA touchpoint (R8) is
   completed with the professional collaborator.

Until then the product stays in its current posture: prototype, human-review
gate mandatory, no real child data beyond what a consenting parent submits for
their own child.

## 6. Consultation & sign-off

- **Internal:** WeGoFwd2020 (owner). ADR-001/002 authors for the safety and
  profiling stances.
- **Required before launch:** DPO / qualified data-protection counsel; where the
  progress engine is in scope, the professional (therapist) collaborator.

| Role | Name | Decision | Date |
|---|---|---|---|
| Owner | WeGoFwd2020 | Draft prepared | 2026-07-01 |
| DPO / counsel | _pending_ | _pending_ | — |

*Review this DPIA quarterly, and whenever the data flow, the provider
configuration, or the set of collected data changes.*
