# M1 outreach — send-ready draft (pediatric OT · advisory · cold email)

**Status:** **Copy approved by owner (2026-07-02).** Not yet sent — sending still
needs a recipient (name + email), the signature block, and the warm-intro choice
below. The message text itself is final and requires no further edits.
**Date:** 2026-07-02 · **Owner:** WeGoFwd2020
**Companion (attach after a positive reply):** `docs/M1_PROFESSIONAL_COLLABORATOR_BRIEF.md` (v0.2)
**Source templates:** `docs/M1_COLLABORATOR_OUTREACH.md`

> This is the finalized version of the pediatric-OT / advisory / cold-email path
> from the templates, with the "decide before sending" choices already resolved:
> **discipline = pediatric OT**, **engagement = advisory, open to compensation**,
> **channel = cold / semi-cold email**. Nothing here is sent automatically — review
> it, fill the three blanks, and send it yourself. (Outward-facing: do not send
> without an explicit go-ahead.)
>
> **2026-07-02 — the owner has approved this copy.** The remaining step is
> operational, not editorial: supply the recipient (name + email) and the signature
> block, pick the warm-intro variant, and send. The send itself stays a human action
> from `wegofwd2020@gmail.com`.

## Before you hit send — three fill-ins only

1. `[Name]` — the recipient's first name.
2. **Signature block** — your name and title (the org + contact are pre-filled).
3. **Warm-intro line (optional)** — if someone referred you, keep the bracketed
   opener and name them; if it's genuinely cold, delete that line (marked below).

Everything else is final copy. After a positive reply, send the 2-page brief and
work the follow-up checklist at the bottom.

---

## Subject

> Defining "ready for the next step" — for a calm-animation tool that supports kids' daily routines

## Body

> Hi [Name],
>
> ⟨warm-intro line — keep **one**: ⟩
> ⟨if referred:⟩ [Mutual contact] suggested I reach out — you help children build
> independence in everyday routines, and you think in terms of the *just-right
> challenge*: when to hold, when to grade up.
> ⟨if cold — delete the line above and use this:⟩ I'm reaching out because you help
> children build independence in everyday routines, and you think in terms of the
> *just-right challenge*: when to hold, when to grade up.
>
> I'm [Your name], [Your title] at WeGoFwd2020. We build **Kathai Chithiram**: a
> parent writes a short story about their child, and we turn it into a calm,
> captioned animation that walks the child through a routine — our first one is a
> tooth-brushing sequence. After a viewing, the parent records a tiny, fixed check:
> **how much support the child needed** (refused / prompted / independent),
> **whether they completed the routine**, and a simple **1–5 mood check-in**.
> Nothing free-text. You'll notice that first field is essentially a prompting
> hierarchy, and the whole record is close to what you'd already track for an ADL.
>
> We'd like that pattern over repeated sessions to *inform* what routine comes next
> — grade the challenge up, hold, or ease. But deciding **what a meaningful signal
> actually is** — how many recent sessions to weigh, what movement toward
> independence suggests readiness to advance, and how to keep a normal off day or a
> dysregulated session from reading as regression — is your judgment, not something
> our engineers should invent. So we've built everything *around* that decision and
> left the decision itself for an OT. (We've gone as far as building the mechanics
> that read your definitions, and deliberately shipped **no thresholds and no
> defaults** — the tool literally cannot run until a professional supplies them.)
>
> A few things I want to be upfront about, because they're the point:
> - **You'd decide; the system only ever suggests.** It never edits a story,
>   generates one, or schedules one on its own — and it's never presented as a
>   clinical measure or assessment.
> - **Every suggestion a therapist accepts still passes a full human review** before
>   it reaches a child.
> - **The data is treated as special-category child data** — minimized, encrypted,
>   never used to train any AI, and permanently deletable on request.
>
> I've written a short brief (2 pages) covering exactly what we'd need from you — the
> window of sessions, the thresholds, and the trend and regulation cut-offs — and the
> guarantees we make in return. Would you be open to a **20–30 minute call** in the
> next couple of weeks to see if it's a fit? This would be an advisory role — happy
> to discuss what works for your time, including compensation.
>
> Thanks either way for the work you do.
>
> Warmly,
> [Your name]
> [Your title] · WeGoFwd2020 · wegofwd2020@gmail.com

---

## Backup: short form (if you'd rather open on LinkedIn / DM first)

> Hi [Name] — I'm building Kathai Chithiram, a tool that turns a parent's short
> story into a calm captioned animation that walks a child through a daily routine
> (our first is tooth-brushing). Parents log a quick per-session check — support
> level (refused / prompted / independent), whether the routine was completed, and a
> 1–5 mood check. We'd like that pattern to *inform* when to grade the challenge up
> — but defining what a meaningful signal is (and keeping a normal off day from
> reading as regression) is an OT's judgment, not an engineering call. The system
> only suggests; a therapist decides, and everything passes human review before a
> child sees it. Could I send a 2-page brief and grab 20 minutes?

## Backup: referral ask (to a mutual contact who can introduce you)

> Hi [Name] — quick ask: I'm looking for a **pediatric OT** willing to advise on one
> specific decision for a tool we're building to support kids' daily routines —
> defining when a child's move toward independence (from simple prompt-level and
> completion feedback) suggests it's time to grade the task up, so we don't let
> engineers invent those thresholds. Light, well-scoped, and the privacy/safety
> groundwork is already done. Anyone come to mind you'd be comfortable introducing
> me to?

---

## After they reply — follow-up checklist

- [ ] Send `docs/M1_PROFESSIONAL_COLLABORATOR_BRIEF.md` (v0.2) after a positive reply.
- [ ] When they respond with definitions (window K, thresholds, trends, framing,
      suggestion tone), record them against **ADR-002 Decision 7.1** as the first
      `ProgressPolicy`, and note it in the M1 backlog entry.
- [ ] Have them review copy/UX for clinical-language creep (Decision 7.4).
- [ ] Only then is the progress **measure** unblocked for build — still gated on the
      7.6 DPIA profiling touchpoint (loop in DPO/counsel).
