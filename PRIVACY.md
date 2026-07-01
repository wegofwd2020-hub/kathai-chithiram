# Kathai Chithiram — Privacy & Data-Handling Policy

**Status:** Draft v0.1 (2026-06-11) · **Owner:** WeGoFwd2020 · **Review cadence:** quarterly, and before any release that changes data flow.

> Kathai Chithiram processes deeply personal information — a parent's written story about *their own child*, often a child with special needs. That makes the data here special-category, child-related data. This document defines how that data is collected, used, stored, retained, and deleted. It is a **commitment**, and the implementation tickets that accompany it exist to make the product match this document.

---

## 1. Scope

This policy covers all data handled by Kathai Chithiram: parent-authored story text, any child identifiers within it, generated scene scripts, and rendered animations.

## 2. Principles (non-negotiable)

1. **Parental control.** The parent (or legal guardian) is the data subject's representative. Only a parent/guardian may submit a story and is the sole controller of what is created and kept.
2. **Data minimization.** Collect only what is needed to generate the animation. Never request the child's full name, date of birth, address, school, diagnosis codes, or any identifier not strictly required.
3. **Purpose limitation.** Story content is used *only* to generate that family's animation. It is never used for advertising, profiling, or shared with third parties for their own purposes.
4. **No training on personal stories.** Parent stories and child data are **never** used to train, fine-tune, or improve any model, and are excluded from any analytics that retain raw content. (See §6 on the LLM provider.)
5. **Privacy by default.** The most protective setting is the default: short retention, local-first where feasible, explicit opt-in for anything broader.

## 3. What we collect

| Data | Why | Sensitivity |
|---|---|---|
| Parent-authored story text (free-form) | Input to scene-script generation | High — may contain child's first name, behaviors, needs |
| Optional child first name / nickname | Personalize narration | High |
| Generated scene script (JSON) | Intermediate artifact for rendering | High (derived from story) |
| Rendered animation (mp4) | The deliverable | High |
| Per-session feedback (prompt level, completed, mood check-in) keyed to a goal | Track engagement/independence over time; may inform a therapist's premise suggestions (ADR-002) | High — behavioral data about the child (**profiling**) |
| Minimal account/contact (if accounts exist) | Deliver output, support | Medium |

**Explicitly out of scope to collect:** child's surname, DOB, address, geolocation, photographs of the child, medical/diagnostic records, biometric data. Per-session feedback is captured as fixed structured primitives only — no free-text notes — and constitutes profiling of a child, so its use is covered by the §8 DPIA touchpoint (see ADR-002).

## 4. How story data flows

```
Parent story ──▶ generation (wegofwd-llm) ──▶ scene script ──▶ renderer ──▶ animation
   (input)         (provider call, §6)        (derived)        (local)      (output)
```

At each hop the data stays scoped to the requesting family. The scene script and animation are byproducts of one story and inherit that story's retention and deletion rules.

## 5. Retention & deletion

- **Default retention:** raw story text is retained only as long as needed to produce and deliver the animation, then deleted within **30 days** unless the parent opts to save it to their account.
- **Right to delete:** a parent can delete a story, its scene script, and its animation at any time; deletion must remove **all** derived artifacts (script + media + caches + backups on the next backup cycle).
- **Hard-delete, not soft-delete** for personal story content — no tombstoned copies of raw text.
- Deletion must be verifiable (a test asserts the artifacts are gone). See implementation ticket.

## 6. LLM provider handling

Generation runs through the shared `wegofwd-llm` seam. Because story text is sent to an LLM provider:

- Use a provider configuration with **zero data retention / no-training** guarantees where available, and record which provider + setting was used.
- Send the **minimum** text necessary; strip or pseudonymize identifiers before the call where the design allows (e.g. replace the child's name with a token, reinsert locally during rendering).
- Never log raw prompts containing story text in plaintext application logs.

## 7. Security

- Encrypt story text and animations at rest and in transit. *(At rest: **done** — KC-5, AES-256-GCM keyed by `KC_STORAGE_KEY`, see `storage/crypto.py`. In transit: pending a network boundary.)*
- Access to personal story data is restricted to the owning parent's session; no broad operator browsing of story content.
- Follow the org `SECURITY.md` conventions once established; until then, the controls in this section are the minimum bar.

## 8. Children's data & legal posture

This product concerns children, frequently children with disabilities. Depending on where it operates it may engage COPPA (US), FERPA (if ever school-distributed), and GDPR/GDPR-K special-category rules (EU). Before any public launch:

- Confirm the legal basis (parental consent) and capture it explicitly.
- Provide a plain-language parent-facing privacy notice (this document is the internal source; a parent-facing version is a separate deliverable).
- If operating in the EU/UK, complete a DPIA (Data Protection Impact Assessment) — strongly warranted given special-category child data.

## 9. Open items (tracked as tickets)

- [x] Implement verifiable hard-delete of story + script + media. *(KC-1: `storage/deletion.py` + 30-day `retention.py`)*
- [x] Implement identifier minimization/pseudonymization before LLM calls. *(KC-2: `privacy/pseudonymize.py`, enforced by the `wegofwd-llm` seam)*
- [x] Record provider no-training/zero-retention configuration. *(KC-2: `ProviderConfig` + `ProviderRequestRecord`)*
- [x] Draft parent-facing privacy notice + consent capture. *(KC-8: `docs/PARENT_PRIVACY_NOTICE.md` + versioned `intake/privacy_notice.py`, shown before consent; `intake.json` records the `privacy_notice_version`. Consent capture: intake flow.)*
- [ ] DPIA before EU launch. *(KC-9: assessment drafted in `docs/DPIA.md`; **not signed off** — launch blocked on KC-5 at-rest encryption, KC-6 ZDR provider key, and DPO/counsel review.)*

*This is a draft for internal alignment and is not legal advice. Have counsel review before relying on it for a public launch.*
