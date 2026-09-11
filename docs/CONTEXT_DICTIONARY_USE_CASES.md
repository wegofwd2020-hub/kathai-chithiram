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
- **Entitlement discovery (ADR-009 D10).** Regulations also map assistance the government has
  *already allocated*; surfacing "what exists for a situation like this, its stated criteria,
  the source, and who decides" is a first-class navigational capability — dated and
  jurisdiction-specific, never an eligibility determination. It is the navigational layer
  running through UC-2, UC-3, UC-4, UC-7 and UC-8.
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

### UC-5 — Respite care and carer burnout (the carer is the person addressed)
- **Persona:** P2 helper-learner — but here the **carer is both the questioner and the beneficiary**. The person the answer serves is the carer, not the person they care for.
- **Query (as asked):** "I care for my adult son with autism full-time and I'm exhausted — what support is there for me?"
- **Domain(s):** caregiving support + respite + carer wellbeing (cross-cuts special-needs and aging)
- **Immediate need:** what respite care is and its forms — in-home respite, adult day programs, short-term residential/facility respite, informal networks — and how to get an actual break.
- **Dependencies / what comes next:** funding for respite (Medicaid HCBS-waiver respite hours, the National Family Caregiver Support Program / ACL, VA caregiver support if a veteran, state caregiver programs) — navigate, don't determine; finding and vetting a respite provider (local directory); the **carer's own neglected health** — burnout, isolation, depression → support groups, counselling, their own overdue medical care; an **emergency backup plan** (who cares for the dependent if the carer is hospitalised); documentation and legal standing for a substitute carer (POA, a care plan); and the long-horizon question — sustainability, and planning for when the carer can no longer provide care. *The dependency society misses: the carer's own survival is the precondition for everything else, and no one asks about it.*
- **Answer layers:** education (what respite is, the signs of burnout, cited) · navigation (local respite providers, caregiver-support programs, funding sources, support groups, who to ask) · products: minimal.
- **Boundary flags:** **strongest D7 case in the log** — a carer in crisis ("I can't do this anymore") must **route to a human**, not receive a corpus answer; this use-case is a concrete reason the risk-of-harm path is a precondition for the assistant surface (ADR-009 D7). Carer mental-health content is **educational, not diagnostic** (ADR-009 D3; CONTENT_SAFETY §3 — no medical claims). Respite-funding eligibility is navigate-not-determine. Decline descriptions of a specific real person (ADR-009 D6).
- **Sources needed:** ACL / National Family Caregiver Support Program (federal), Medicaid waiver respite provisions, VA caregiver support, Michigan caregiver programs and local respite directories (state/local, freshness-sensitive — ADR-011), reputable carer mental-health resources.
- **Status:** captured — notable for flipping *who* is addressed (the carer) and for being the log's clearest test of the D7 escalation path.

### UC-6 — AAC: communication aids for a non-speaking person
- **Persona:** P2 helper-learner (parent / carer / aide) with a strong P3 lifespan thread — the system grows with the person.
- **Query (as asked):** "My son is non-speaking — what communication options are there and how do we start?"
- **Domain(s):** special-needs practice + AAC / assistive technology + device products + local services (speech-language pathology)
- **Immediate need:** what AAC (augmentative and alternative communication) is, and its spectrum — unaided (sign, gestures), low-tech (picture boards, PECS), high-tech (speech-generating devices, tablet apps, eye-gaze) — plus the two things families are rarely told up front: **AAC does not hinder speech development** (a persistent myth), and **presume competence**.
- **Dependencies / what comes next:** assessment by a **speech-language pathologist** to match the system to the person (the device is chosen *after* this, not before); **funding** — speech-generating devices are often covered as durable medical equipment / an SGD benefit by Medicaid/insurance → navigate, don't determine; **training of communication partners** (family, teachers, aides) — AAC fails without it, and the biggest failure mode is a device that's technically fine but socially unsupported; vocabulary customisation and ongoing programming; charging, mounting, durability, repair and replacement; **school integration** (the device travels to school; IDEA assistive-technology access); a **low-tech backup** when the device is down; and the lifespan axis — vocabulary and system grow as the person develops (P3). *The dependency society misses: **AAC abandonment** — devices are commonly given up not for technical reasons but because the support system around them was never built. The need is the support, not the gadget.*
- **Answer layers:** education (AAC types, presume-competence, myths debunked, cited) · navigation (find an SLP / AAC specialist, the assessment, the funding path, partner-training resources) · products (Layer B: devices, apps, mounts, switches, eye-gaze — labelled, ADR-013).
- **Boundary flags:** **the log's cleanest test of the commercial guardrail** — "which device should we buy?" is exactly what ADR-009 D3 forbids answering individually and what ADR-013 D2/D3 keeps out of Layer A: the honest answer is "an SLP assessment determines fit; here are the categories," never "buy device X". Speech-generating devices are often **regulated / durable medical equipment and high-cost** → ADR-013 D4 tier check; the commercial layer must not push a specific expensive device the assessment hasn't chosen. Device funding eligibility is navigate-not-determine. Decline descriptions of a specific real person (ADR-009 D6).
- **Sources needed:** ASHA AAC guidance, AAC practice/research, Medicaid/Medicare speech-generating-device coverage rules, IDEA assistive-technology provisions, local SLP / AAC clinic directories (state/local, freshness-sensitive — ADR-011).
- **Status:** captured — the case where the ADR-013 commercial boundary does the most work (assessment decides, not the store).

### UC-7 — Mobility and fall-prevention in the home for a senior
- **Persona:** P2 helper-learner (an adult child / carer) with a P3 lifespan thread — needs increase as mobility declines.
- **Query (as asked):** "My mother is unsteady on her feet — how do I make her home safer so she doesn't fall?"
- **Domain(s):** aging + built-environment accessibility + mobility (crosses into health / fall risk)
- **Immediate need:** home modifications that reduce falls — grab bars (bathroom, by stairs), removing trip hazards (loose rugs, cords), lighting (night and motion-activated), non-slip surfaces, stair rails, a shower chair and raised toilet seat, threshold ramps.
- **Dependencies / what comes next:** a professional **home-safety / occupational-therapy assessment** that matches modifications to the person; the person's **own fall-risk factors, which the home can't fix** — a medication review (many drugs affect balance), a vision check, proper footwear, and **strength/balance training** (PT, evidence-based programmes) — so the home is one lever among several; **mobility-aid fitting and training** (a badly fitted cane or walker *causes* falls); an **emergency-response plan** (a medical-alert / personal-emergency-response device) for the fall that happens anyway; **funding** for modifications (Medicaid-waiver home-mod benefits, the Area Agency on Aging, VA) → navigate, don't determine; who installs (a contractor or a certified aging-in-place specialist). *The dependency society misses: people grab-bar the bathroom and stop there, skipping the medication review and balance training that move the risk more.*
- **Answer layers:** education (home-safety measures and the multi-factorial nature of falls, cited) · navigation (an OT home assessment, PT/balance programmes, local aging-in-place installers, funding, medical-alert options, who to ask) · products (Layer B: grab bars, ramps, shower chairs, walkers, medical-alert devices — labelled, ADR-013).
- **Boundary flags:** **crosses into health — stays educational, never medical advice.** "Some medications affect balance — ask a pharmacist or doctor to review them" is fine; naming a drug to stop is not (ADR-009 D3; CONTENT_SAFETY §3 — no medical claims). A **recurring-subscription commercial angle** appears here (medical-alert monitoring) — a nuance for ADR-013's disclosure (an ongoing fee, not a one-off purchase); some devices are DME → ADR-013 D4 tier. Funding eligibility is navigate-not-determine. A recent fall with injury is **urgent** — route to emergency services, don't answer as a corpus query (D7-adjacent). Decline descriptions of a specific real person (ADR-009 D6).
- **Sources needed:** CDC STEADI fall-prevention materials (federal, public domain), ACL / Area Agency on Aging, Medicaid-waiver home-modification provisions, aging-in-place / CAPS resources, PT/OT fall-prevention practice, local OT and contractor directories (state/local, freshness-sensitive — ADR-011).
- **Status:** captured — the case that most tests the health/education line and introduces subscription-based commercial listings.

### UC-8 — Employment and workplace accommodations (the self-advocate)
- **Persona:** **self-advocate** — the person with the disability asking for *themselves* (a persona angle beyond P2/P3; also reached by a job coach or family). A new major domain, reinforcing the broadened scope (ADR-009 D9).
- **Query (as asked):** "I have ADHD and I'm starting a new job — what workplace accommodations can I ask for, and how?"
- **Domain(s):** employment + disability rights (ADA Title I) + assistive technology
- **Immediate need:** what "reasonable accommodations" are under the ADA, examples matched to different needs (flexible schedule, a quiet workspace, written instructions, assistive tech, scheduled breaks), and how the request works — the employer/employee **interactive process**.
- **Dependencies / what comes next:** the **disclosure decision** — whether, when and how much to disclose a disability, a personal and high-stakes choice with real trade-offs (navigate, never advise); documentation an employer may request; what counts as "reasonable" vs an employer's "undue hardship" defence; rights and the process if a request is denied or met with retaliation (the EEOC complaint route) → navigate, don't determine an outcome; the **benefits interaction** — if on SSI/SSDI, working affects benefits (SSA work incentives / Ticket to Work) → navigate; vocational rehabilitation and supported employment (links to UC-4 transition); and re-visiting accommodations as the role or condition changes. *The dependency society misses: the accommodation is the easy part — the disclosure decision and the interactive-process skills are what actually determine whether someone keeps the job.*
- **Answer layers:** education (what ADA accommodations are, examples, the interactive process, cited) · navigation (how to request, the Job Accommodation Network, EEOC and ADA National Network, vocational rehab, and — for a dispute — an employment attorney) · products: minimal (some assistive tech).
- **Boundary flags:** **strong ADR-009 D6 test.** General "what accommodations exist for ADHD, and how does the interactive process work?" is educational and fine; "what should *I* do in *my* dispute with *my* employer?" is individualised advice about a real person — **navigate to a human** (JAN, EEOC, an employment attorney), don't answer. "Should I disclose?" and "will I win an EEOC complaint?" are navigate-not-determine and legal-information-not-advice. Benefits-while-working is navigate-not-determine. Decline a description of a specific real person (ADR-009 D6).
- **Sources needed:** EEOC ADA Title I guidance (federal, public domain), the **Job Accommodation Network (JAN)** (the canonical free resource), ADA National Network, SSA work-incentive / Ticket to Work rules, vocational-rehabilitation guidance (state-level — ADR-011 freshness).
- **Status:** captured — introduces the self-advocate persona and the disclosure decision; the clearest test of D6's general-education vs individual-advice line.

### UC-9 — Guardianship at 18, and its less-restrictive alternatives
- **Persona:** P3 lifespan navigator (a parent of a young adult with an intellectual/developmental disability approaching majority); also reached by the young adult themselves (self-advocate).
- **Query (as asked):** "My son with an intellectual disability turns 18 soon — do we need guardianship, and what are the alternatives?"
- **Domain(s):** legal / decision-making rights + lifespan transition + special-needs
- **Immediate need:** understand that at 18 a person becomes a legal adult with the right to make their own decisions, and the **spectrum of decision-making support from least to most restrictive** — supported decision-making (least restrictive), power of attorney, a healthcare proxy, a representative payee, limited/partial guardianship, and full guardianship (most restrictive, which removes civil rights). The governing principle: **least-restrictive alternative first** — guardianship should not be the default.
- **Dependencies / what comes next:** the decision has to be made **around 18** (timing, before/at majority); a capacity assessment; if guardianship is pursued, the court process (petition, hearing, an attorney, cost, and *ongoing* reporting and renewal duties); choosing the **domains** it covers (medical, financial, residential — it can be limited to some); interactions with benefits (a representative payee for SSI), healthcare (HIPAA authorisation), and education (IEP rights transfer to the student at majority); the **rights lost** under full guardianship (to vote, marry, contract, choose where to live — varying by state); reversibility and restoration of rights; and the alternatives that avoid it entirely (a supported-decision-making agreement, POA, an ABLE account). *The dependency society misses: guardianship is often presented as automatic at 18, when least-restrictive alternatives preserve autonomy — families are rarely told there is a choice.*
- **Answer layers:** education (the decision-making spectrum, the least-restrictive principle, the rights implications, cited) · navigation (legal aid / the state Protection & Advocacy org, a special-needs or elder-law attorney, the court self-help process, supported-decision-making resources) · products: none.
- **Boundary flags:** **the log's highest-stakes navigate-not-advise case** — the system explains the options, the process and the rights at stake and points to an attorney / disability-rights org; it **never** says "you should get guardianship" or "you don't need it" (a legal decision that can remove civil rights). **Strongly state-specific** (guardianship law varies a lot by state — Michigan first, ADR-009 D4). This use-case is the purest expression of the **mission** — *presume competence, address the person, don't strip autonomy by default* (aligns with ADR-001). Decline a description of a specific real person (ADR-009 D6).
- **Sources needed:** state guardianship statutes (Michigan first), the National Resource Center for Supported Decision-Making, ACL, the state Protection & Advocacy (P&A) system, ABA and court self-help materials (state-level, freshness-sensitive — ADR-011).
- **Status:** captured — the highest-stakes navigate-not-advise case and the clearest ethical expression of "address, not label."

---

## Backlog — use-cases to detail over time

The initial seed list is now fully detailed above (UC-1…UC-9). New scenarios land here first as a one-line stub, then become a full entry above when detailed.

> Add new use-cases as real questions surface — from the owner's own family situations
> (2 special-needs, 2 senior) and, later, from what actual users ask.
