# Context dictionary — use-case log

A living catalogue of the questions the **context dictionary** (the `wegofwd-arivu` corpus,
ADR-009) is meant to answer. Each entry is a real scenario, written the way a person would
actually ask it, with the **immediate need** *and* the **dependencies that solving it
creates** — because the mission is to *address the person, not the label* (ADR-009 Mission):
serve the next need, not just the question in front.

## What this log is for

1. **Domain prioritisation (ADR-009 D9).** Scope is broad by vision, incremental by domain.
   The use-cases that recur here are the evidence for which domain to build next
   (special-needs practice → aging → built-environment/accessibility → …).
2. **The eventual eval set.** When the practice-assistant surface (ADR-009 Surface 2) is
   built, these scenarios become its test cases — including whether it surfaces the
   *dependencies*, not just the immediate answer. (The eval set will live with the corpus in
   `wegofwd-arivu` per ADR-012; this log is where the scenarios are gathered first.)
3. **A design forcing-function.** The "dependencies / what comes next" column is what pushes
   the corpus toward modelling relationships between needs, not just retrievable passages
   (an ADR-010 concern).

## Boundaries every entry inherits

- **Educate, cite, never advise (ADR-009 D3).** Answers explain, cite, present options and
  say *who to ask next*. Anticipating dependencies stays "people who solved X commonly need Y
  next [source]" — never "you must do Y".
- **Navigate, never determine.** Eligibility-flavoured questions ("will insurance cover
  this?", "does he qualify?") are navigated (what the term means, what the plan's own
  documents say, the appeal path, who decides) — never adjudicated.
- **No personal data (ADR-009 D6).** A question describing a specific real individual is
  declined and redirected, not answered or stored. Entries below use generic personas.
- **Risk-of-harm routes to a human (ADR-009 D7).** "What do I do when he hits himself" is not
  a corpus answer; it routes to a person and real resources.
- **Commerce is Surface-2-only, labelled, and never bends the answer (ADR-013).** Product
  listings sit in a separate, disclosed layer beneath the cited education — never in the
  child animation.

## Entry template

```
### UC-N — <short title>
- **Persona:** P2 helper-learner | P3 lifespan navigator | P1 parent (Kathai Chithiram) | …
- **Query (as asked):** "<the user's own words>"
- **Domain(s):** special-needs practice | aging/lifespan | accessibility (built env) | …
- **Immediate need:** <the question in front>
- **Dependencies / what comes next:** <the recurring, downstream, adjacent needs this sets up>
- **Answer layers:** education (Layer A) · navigation (local/who-to-ask) · products (Layer B, ADR-013)
- **Boundary flags:** <D3 determination risk? regulated products? D6 personal data? D7 risk-of-harm?>
- **Sources needed:** <what the corpus must hold to answer this>
- **Status:** captured | prioritised | in corpus | has eval
```

---

## Use-cases

### UC-1 — A calm story for a child's routine (the shipping surface)
- **Persona:** P1 parent (Kathai Chithiram, Surface 1)
- **Query (as asked):** "Silas is scared of brushing his teeth — can you make something that helps him?"
- **Domain(s):** special-needs practice
- **Immediate need:** a short, calm, captioned social narrative the child can watch.
- **Dependencies / what comes next:** other daily routines (bath, haircut, first dental visit); the same child needing different framing at 6 vs 12 vs 19 (the lifespan axis, ADR-009 D2/P3).
- **Answer layers:** this surface *produces an artefact*, not text — it consumes the corpus for grounded generation rather than serving answers.
- **Boundary flags:** child data (full ADR-001 apparatus); **no commerce anywhere near this surface** (ADR-013 D1).
- **Sources needed:** desensitisation / routine-support practice (already the KC-6/ADR-008 corpus goal).
- **Status:** in production (Surface 1).

### UC-2 — Making a home work for a senior with hearing loss
- **Persona:** P2 helper-learner (an adult child / carer setting up a home)
- **Query (as asked):** "What capabilities does a house need for a senior citizen with a hearing disability?"
- **Domain(s):** accessibility (built environment) + aging + hearing
- **Immediate need:** the accommodations a home should have — visual/tactile smoke and CO alarms, doorbell and phone signallers, layout and lighting for lip-reading and sightlines.
- **Dependencies / what comes next:** installation and who installs it; interaction with rental vs owned housing (Fair Housing reasonable-modification rights); maintenance and testing of alerting devices; what changes if vision or mobility also declines with age; emergency planning when the person can't hear an alarm.
- **Answer layers:** education (accommodation types, cited) · navigation (local installers, an OT home assessment, who to ask) · products (Layer B: signallers, visual alarms — labelled, ADR-013).
- **Boundary flags:** some alerting devices carry safety claims → ADR-013 D4 tier check; "will my insurance/landlord pay" is navigate-not-determine.
- **Sources needed:** ADA/Fair Housing built-environment guidance, accessibility standards, local installer/OT directories (a distinct local-data + freshness problem, ADR-011).
- **Status:** captured — the founding example of the broadened scope (ADR-009 D9).

### UC-3 — Keeping a senior's hearing aid working (the dependency chain)
- **Persona:** P3 lifespan navigator (a carer supporting an aging parent)
- **Query (as asked):** "What does a senior with hearing challenges need around a hearing aid?"
- **Domain(s):** aging + hearing + local resources
- **Immediate need:** the device itself — types of hearing aids, what fits which kind of hearing loss, and cited plain-language explanation.
- **Dependencies / what comes next:** **recurring batteries** (and their cost); **dexterity** — changing tiny batteries with aging hands, so rechargeable options matter; a **backup** device when one fails; **routine audiology follow-ups** and refitting; **phone/TV/loop compatibility**; cleaning and moisture care; what to do when it's lost. *This is the anticipatory capability in one case: solving "get a hearing aid" opens six more needs the person is rarely told about.*
- **Answer layers:** education (device and consumable types, cited) · navigation (local audiology clinics, follow-up cadence, who fits and repairs) · products (Layer B: aids, batteries, rechargeable kits, dry-boxes — labelled, ADR-013).
- **Boundary flags:** hearing aids can be regulated devices → ADR-013 D4 tier; "is it medically necessary / will insurance cover it" is navigate-not-determine (explain the term, the plan's documents, the appeal path, who decides).
- **Sources needed:** audiology practice guidance, device/consumable references, **local clinic directories** (stale-fast local data, ADR-011 freshness).
- **Status:** captured — the owner's worked example of "address, not label" and the dependency chain.

### UC-4 — Aging out: the school-to-adult-services transition
- **Persona:** P3 lifespan navigator (a parent/carer of a teen with disabilities approaching adulthood)
- **Query (as asked):** "My daughter has an intellectual disability and turns 16 — what happens when she ages out of school, and what do I need to do now?"
- **Domain(s):** special-needs practice + lifespan/transition + adult-services navigation (US; Michigan-first per ADR-009 D4)
- **Immediate need:** understand the "cliff" — school-based IDEA services are an **entitlement** that ends (through age 21/22 depending on state); adult services are **eligibility-based** and often waitlisted. What changes, and on what timeline.
- **Dependencies / what comes next:** transition planning written into the IEP (starts ~14–16); legal decision-making status settled **before 18** (guardianship vs supported decision-making vs power of attorney); adult-services applications filed **early** because waitlists are long — Medicaid HCBS waivers, the state developmental-disability agency, vocational rehabilitation, SSI reassessed as an adult at 18, an ABLE account; pediatric→adult healthcare transfer; day programs / supported employment / housing (also waitlisted). *The buried dependency society misses: you must apply years early, and almost no one tells families that in time — the clearest case of "address, not label".*
- **Answer layers:** education (what the transition is, the entitlement-vs-eligibility shift, cited) · navigation (the applications, timelines, waitlists, who decides, the state DD agency and VR office) · products: minimal — this is services, not products.
- **Boundary flags:** **heavy navigate-not-determine** — waiver / SSI / VR eligibility is explained and navigated, **never adjudicated** ("does she qualify?" → what it is, the application, the waitlist, who decides); guardianship is legal information plus *who to ask* (an attorney), not advice; **strongly state-specific** (ADR-009 D4, Michigan first); carer distress possible (route per D7).
- **Sources needed:** IDEA/OSEP transition guidance (federal, public domain), CMS Medicaid HCBS-waiver material, SSA SSI/SSDI adult rules, Michigan developmental-disability agency + Vocational Rehabilitation guidance and directories (state-level, freshness-sensitive — ADR-011).
- **Status:** captured — **high priority.** ADR-009 D2/P3: "highest real-world need, hardest corpus, highest hazard."

---

## Backlog — use-cases to detail over time

Seed list; expand as scenarios come up. Each becomes a full entry above when detailed.

- Respite care and carer burnout — what support exists for the *carer*.
- Communication aids (AAC) for a non-speaking person — devices, training, dependencies.
- Mobility and fall-prevention in the home for a senior (built-environment + aging).
- "What changes when my child turns 18" — guardianship vs supported decision-making (navigate, never determine).
- Employment supports and workplace accommodations (ADA, accessibility domain).

> Add new use-cases as real questions surface — from the owner's own family situations
> (2 special-needs, 2 senior) and, later, from what actual users ask.
