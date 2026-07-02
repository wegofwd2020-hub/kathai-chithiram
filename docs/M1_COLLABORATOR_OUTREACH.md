# M1 professional-collaborator outreach — templates

**Status:** Draft v0.1 (2026-07-01) · **Owner:** WeGoFwd2020 · **Companion to:**
`docs/M1_PROFESSIONAL_COLLABORATOR_BRIEF.md`

> **A finalized, send-ready version exists:** `docs/M1_OUTREACH_SEND_READY.md`
> (pediatric OT · advisory · cold email — the "decide before sending" choices
> already resolved, three fill-ins left). This file remains the source of the
> per-discipline / per-channel variants to draw from for other paths.

> Templates for reaching a trained therapist / professional collaborator to
> satisfy ADR-002 Decision 7.1 — the precondition that a professional (not
> engineering) defines the progress signal before the M1 engine is built.
> Personalize the `[bracketed]` placeholders before sending. Keep the framing
> honest: we are asking them to define clinical judgment and to keep our language
> from ever reading as a diagnosis or clinical measurement (CONTENT_SAFETY.md §3).
> Send `docs/M1_PROFESSIONAL_COLLABORATOR_BRIEF.md` as the follow-up.

## Before you send — two things to decide

These change the tone more than the wording does:

1. **Engagement model** — advisory volunteer, paid consultant, or formal partner?
   The email below assumes "advisory, open to discussing compensation." If it is
   paid from the outset, say so plainly — it reads as more serious and respectful
   of their time.
2. **Discipline** — the ask reads a little differently for a pediatric OT, an SLP,
   a child psychologist, or a special-ed teacher. The brief is discipline-neutral;
   tailor the "why you" line and the examples to whoever you have in mind.

---

## 1. Primary email (warm / semi-cold)

**Subject:** Would you help us define what "progress" should mean — for a calm-animation tool for kids with special needs?

> Hi [Name],
>
> [I'm reaching out because / [Mutual contact] suggested you as someone who —]
> you work closely with children with special needs and think carefully about how
> progress actually shows up day to day.
>
> I'm [your name], [role] at WeGoFwd2020. We build **Kathai Chithiram**: a parent
> writes a short story about their child, and we turn it into a calm, captioned
> animation the child can follow. After a viewing, the parent records a tiny,
> fixed check — how much help the child needed, whether they completed the
> routine, and a simple 1–5 mood check-in. Nothing free-text.
>
> We'd like a child's real response over time to *inform* what story comes next.
> That's where we need you — and where we've deliberately **stopped**. Deciding
> what a meaningful signal is (how many recent sessions to look at, what patterns
> suggest a child is ready to advance vs. hold, how to avoid reading normal
> day-to-day variance as regression) is clinical judgment, not something our
> engineers should invent. So we've built everything *around* that decision and
> left the decision itself for a professional.
>
> Concretely, we're asking you to define: the window of sessions to consider, the
> thresholds that count as a real signal, and — just as important — to keep our
> language honest so nothing we show ever reads as a diagnosis or clinical
> measurement.
>
> A few things I want to be upfront about, because they're the point:
> - **You'd decide; the system only ever suggests.** It never edits a story,
>   generates one, or schedules one on its own.
> - **Every suggestion a therapist accepts still goes through a full human review**
>   before it reaches a child.
> - **The data is treated as special-category child data** — minimized, encrypted,
>   never used to train any AI, and permanently deletable on request.
>
> I've written a short brief (2 pages) that lays out exactly what we'd need from
> you and the guarantees we make in return — happy to send it over. Would you be
> open to a **[20–30 minute] call** in the next couple of weeks to see if it's a
> fit? [This would be an advisory role — happy to discuss what works for your
> time, including compensation.]
>
> Thanks either way for the work you do.
>
> Warmly,
> [Your name]
> [Title · WeGoFwd2020 · contact]

---

## 2. Short version (LinkedIn / DM / intro)

> Hi [Name] — I'm building Kathai Chithiram, a tool that turns a parent's short
> story into a calm captioned animation for a child with special needs. We want a
> child's response over repeated viewings to *inform* what comes next — but we've
> deliberately not built the "is this progress?" logic, because that's clinical
> judgment, not an engineering call. We're looking for a professional to define
> what a meaningful signal actually is (and keep our framing honest — the system
> suggests, a therapist always decides, and everything passes human review before
> a child sees it). Could I send you a 2-page brief and grab 20 minutes? Would
> value your take.

---

## 3. Referral ask (to a mutual contact who can introduce you)

> Hi [Name] — quick ask: I'm looking for a [pediatric OT / speech-language
> pathologist / special-ed or child psychologist] willing to advise on one
> specific decision for a tool we're building for kids with special needs —
> defining what counts as meaningful "progress" from simple per-session feedback,
> so we don't let engineers invent clinical thresholds. Light, well-scoped, and
> we've done the privacy/safety groundwork already. Anyone come to mind you'd be
> comfortable introducing me to?

---

## Tailored: pediatric occupational therapist (OT)

OT-specific versions of the three templates above. The hooks that land with an OT:
our `prompt_level` (refused / prompted / independent) **is** a prompting hierarchy;
the per-session record mirrors how an OT already tracks an ADL; the ask is framed
as *when to grade the just-right challenge up vs. hold*; and it names the trap an
OT would most want guarded — a normal off day or a dysregulated session reading as
regression. The tooth-brushing story is a concrete ADL hook.

### Email

**Subject:** Defining "ready for the next step" — for a calm-animation tool that supports kids' daily routines

> Hi [Name],
>
> [I'm reaching out because / [Mutual contact] suggested you —] you help children
> build independence in everyday routines, and you think in terms of the
> *just-right challenge*: when to hold, when to grade up.
>
> I'm [your name], [role] at WeGoFwd2020. We build **Kathai Chithiram**: a parent
> writes a short story about their child, and we turn it into a calm, captioned
> animation that walks the child through a routine — our first one is a
> tooth-brushing sequence. After a viewing, the parent records a tiny, fixed
> check: **how much support the child needed** (refused / prompted / independent),
> **whether they completed the routine**, and a simple **1–5 mood check-in**.
> Nothing free-text. You'll notice that first field is essentially a prompting
> hierarchy, and the whole record is close to what you'd already track for an ADL.
>
> We'd like that pattern over repeated sessions to *inform* what routine comes
> next — grade the challenge up, hold, or ease. But deciding **what a meaningful
> signal actually is** — how many recent sessions to weigh, what movement toward
> independence suggests readiness to advance, and how to keep a normal off day or a
> dysregulated session from reading as regression — is your judgment, not something
> our engineers should invent. So we've built everything *around* that decision and
> left the decision itself for an OT.
>
> A few things I want to be upfront about, because they're the point:
> - **You'd decide; the system only ever suggests.** It never edits a story,
>   generates one, or schedules one on its own — and it's never presented as a
>   clinical measure or assessment.
> - **Every suggestion a therapist accepts still passes a full human review**
>   before it reaches a child.
> - **The data is treated as special-category child data** — minimized, encrypted,
>   never used to train any AI, and permanently deletable on request.
>
> I've written a short brief (2 pages) covering exactly what we'd need from you —
> the window, the thresholds, the trend and regulation cut-offs — and the
> guarantees we make in return. Would you be open to a **[20–30 minute] call** in
> the next couple of weeks? [This would be an advisory role — happy to discuss
> what works for your time, including compensation.]
>
> Thanks either way for the work you do.
>
> Warmly,
> [Your name]
> [Title · WeGoFwd2020 · contact]

### Short (LinkedIn / DM / intro)

> Hi [Name] — I'm building Kathai Chithiram, a tool that turns a parent's short
> story into a calm captioned animation that walks a child through a daily routine
> (our first is tooth-brushing). Parents log a quick per-session check — support
> level (refused / prompted / independent), whether the routine was completed, and
> a 1–5 mood check. We'd like that pattern to *inform* when to grade the challenge
> up — but defining what a meaningful signal is (and keeping a normal off day from
> reading as regression) is an OT's judgment, not an engineering call. The system
> only suggests; a therapist decides, and everything passes human review before a
> child sees it. Could I send a 2-page brief and grab 20 minutes?

### Referral ask (to a mutual contact)

> Hi [Name] — quick ask: I'm looking for a **pediatric OT** willing to advise on
> one specific decision for a tool we're building to support kids' daily routines —
> defining when a child's move toward independence (from simple prompt-level and
> completion feedback) suggests it's time to grade the task up, so we don't let
> engineers invent those thresholds. Light, well-scoped, and the privacy/safety
> groundwork is already done. Anyone come to mind you'd be comfortable introducing
> me to?

---

## Follow-up checklist

- [ ] Send `docs/M1_PROFESSIONAL_COLLABORATOR_BRIEF.md` after a positive reply.
- [ ] When they respond with definitions (window K, thresholds, trends, framing,
      suggestion tone), record them against **ADR-002 Decision 7.1** and check off
      7.1 in `TICKETS/M1-progress-engine.md`.
- [ ] Have them review copy/UX for clinical-language creep (Decision 7.4).
- [ ] Only then is the progress **measure** unblocked for build (still gated on
      7.6 DPIA confirmation).
