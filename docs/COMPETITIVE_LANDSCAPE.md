# Competitive & Adjacent-Systems Landscape — the context dictionary

**Point-in-time scan, US, verified live September 2026.** Every named player was checked
against a source; unverified items are flagged explicitly. This is a dated snapshot — the
funded players move fast (see §Risks). Re-run before any strategic decision that leans on it.

> **Why this doc exists.** It answers "is anyone else doing what wegofwd-arivu does?" and
> maps where we're differentiated vs crowded. It also surfaced a **load-bearing corpus-rights
> finding** (§d) that feeds ADR-011. Governs nothing; informs positioning and the corpus plan.

**Our five pillars (the yardstick):** (1) citation-grounded RAG, every claim cited;
(2) "educate, always cite, never advise"; (3) entitlement discovery — surface what exists +
criteria + **who-decides**, never adjudicate "you qualify"; (4) dependency-aware/anticipatory;
(5) span disability **and** aging **and** accessibility, non-clinical, low personal data.

---

## Bucket 1 — Special-needs care navigation for parents

| Player | What / who | Model | How it differs from us |
|---|---|---|---|
| **Undivided** (undivided.io) | Parent platform for IEP/504, regional-center services, benefits; AI "Andy" + human Navigators + knowledge base. CA-heavy. | Consumer subscription ~$19/mo | **Advocacy-driven, not never-advise** (drafts letters, "fights alongside you"); human-concierge-heavy; disability-children-only (no aging); high personal data; no per-claim citation. Strongest overall parent competitor. |
| **Special Needs Navigator ("Sage")** (specialneedsnavigator.us) | AI guide to SSI, Medicaid waivers, Special Needs Trusts, VA/DAC benefits. | Freemium $14.99–$34.99/mo | **Closest philosophical match** — educational-not-advisory, entitlement-focused, near-identical "not advice, verify with agencies" disclaimer. Gaps: **no source citations** (single-expert model, not transparent RAG); disability/benefits-only, no aging/accessibility. |
| **RethinkCare** (rethinkcare.com) | Employer neurodiversity/disability platform; e-learning + live BCBA consults. | Employer benefit | Clinician-backed behavioral guidance (advises); employer-gated; no citations; no aging span. |
| **Included Health** (includedhealth.com) | General healthcare navigation via care teams + AI. | Employer / health-plan | Broad clinical/cost navigation, not disability-entitlement; concierge; high PHI. |
| **Cortica, Hopebridge, Little Otter** | Clinical autism/behavioral/pediatric-MH **treatment** providers. | Insurance / Medicaid-reimbursed | **Opposite of us** — they diagnose and treat. |
| **Cognoa / Canvas Dx** (cognoa.com) | **FDA-authorized** AI autism *diagnostic aid* (18–72 mo). | Regulated device | The exact regulated diagnostic thing we must never be. |

**Corrections / flags:** **Elemy** defunct as a care provider (shut in-person ABA 2022 → "Tilly", now ABA practice-management software). **Brightline** heavily restructured (cut ops in 45 states, late 2024). **"Wonder" (special needs) — UNVERIFIED**, no current company found. **AbleSpace** is a professional/school tool (Bucket 4), not a parent navigator. **Nabla** ruled out (clinician scribe).

---

## Bucket 2 — Benefits / entitlement screening & navigation

The defining contrast: **almost every screener estimates eligibility** ("you likely qualify") — the opposite of our never-adjudicate stance.

| Player | What / who | Model | Differs from us |
|---|---|---|---|
| **mRelief** (mrelief.com) | ~3-min SNAP screener, web+SMS, all states. | Nonprofit/philanthropy | Estimates eligibility AND files; single-program; no citations. |
| **BenefitsCheckUp / NCOA** (benefitscheckup.org) | Matches to 2,000+ programs; serves **older adults AND people with disabilities**. | Nonprofit | Closest to our *span*, but predicts ("may be eligible") and **does not cite** regulations. |
| **Benefit Kitchen** (benefitkitchen.com) | To-the-dollar eligibility + amount estimates, 25 programs. | B2B SaaS / white-label | Maximal adjudication (computes dollars). **Notably anticipatory** — predicts recertification loss (the only "dependency-aware" feature found in the wild), but for dollars, not entitlement discovery. |
| **USA.gov Benefit Finder** (usa.gov/benefit-finder) | Federal questionnaire, 1,000+ programs. | Government, free | "Determines eligibility"; static form; no per-claim citation. **Standalone Benefits.gov is deprecated → USA.gov.** |
| **findhelp** (formerly Aunt Bertha) | Largest social-care referral network, 970k+ programs; screening add-on. | Free to seekers; institutions pay SaaS. TPG-recapitalized 2026. | Referral-and-fulfillment platform sold to institutions; screening configurable, not cited education. |
| **Unite Us, Single Stop, 211, Propel** | Closed-loop referral infra / student wraparound / human hotline / EBT management. | SaaS / gov / nonprofit / consumer | Coordination, human navigation, or post-enrollment management — none are cited never-adjudicate education. |
| **Nava PBC** (navapbc.com) | AI for **caseworkers**; document/summary/referral. | Gov contract | **Cites sources so navigators can verify; keeps human deciding.** Close on posture — but caseworker-facing, benefits-only. |
| **Code for America × Anthropic** SNAP policy tool | Caseworker Q&A: plain-language answer **with cited sources**, on federal regs + state manuals. | Nonprofit + gov | **Closest philosophical match anywhere** — cites sources, explicitly "clarity on policy, **not a decision** on eligibility; the decision stays with you." But caseworker-only, single-program (SNAP). (Same org's **GetCalFresh** is the opposite: estimates + files.) |

**Flags:** "ExplorerAI" / "Benji" as benefits screeners — **unverifiable**. Self-reported scale figures (findhelp, NCOA) not independently audited.

---

## Bucket 3 — Caregiving / aging navigation

| Player | What / who | Model | Differs from us |
|---|---|---|---|
| **Wellthy** (wellthy.com) | Care concierge, 2M lives; 200+ social workers/nurses. Aging + disability. | Employer / health-plan | Human-concierge; advises; high PII; citations not evidenced. |
| **Cariloop** (cariloop.com) | Human Care Coaches, full lifecycle. **Explicitly refuses referral/lead-gen fees.** | Employer benefit | Human-coordinator, advises/recommends; no per-claim citation. Absorbing Grayce's clients. |
| **ianacare** (ianacare.com) | Navigators + AI care-plans; **CMS GUIDE dementia model**. | Employer / health-plan / Medicare | Advises; aging-weighted; no citation discipline. |
| **Homethrive** (homethrive.com) | Care Guides; spans aging, chronic illness, **neurodivergence, disability**. | Employer / Medicare Advantage | Broadest incumbent scope, but human-advice + predictive, not cited education. |
| **Chapter** (chapter.com) | AI Medicare navigation, **conflict-free**. **$100M Series E, ~$3B valuation, >$100M ARR (Apr 2026).** | Free to seniors | **The well-funded near-neighbor.** But **aging/Medicare-only**; recommends plans (advises). |
| **Hera / "Juno"** (hellohera.com) | AI + human "Heroes" coordinating senior care; Medicare + Medicaid. $27M Series A (Jun 2026). | **Medicare CCM-reimbursed — 90% pay $0** | Strongest hybrid operational analog to entitlement-navigation, but paid concierge that advises + touches eligibility; aging-only. |
| **Understood Care** (understoodcare.com) | Medicare advocates + AI; **cites primary CMS/SSA sources (26 listed)**; ranks plans. | Medicare-covered | **Only aging player that visibly cites primary sources** — but cites to justify *plan rankings* (a commercial recommendation), violating "never advise." |
| **A Place for Mom** (aplaceformom.com) | Senior-living referral. | **Referral fee (~1 mo rent/move-in)** | The **anti-pattern**: 2024 Senate Aging Committee found families shown only commission-paying facilities. |
| **TCARE** (tcare.ai) | B2B burnout intervention; **covers developmental disability + veterans + aging**. | B2B | Closest on *scope*, but not a cited knowledge layer. |

**Corrections:** **"Herald" does not exist — it is Hera.** **Torchlight** acquired by **LifeSpeak (2021)** — still active. **Grayce** winding down (referring clients to Cariloop, Nov 2025). Papa/Vesta = human/clinical, aging-only. "CareYaya $690B NVIDIA acquisition" is a **hoax**.

---

## Bucket 4 — IEP / special-education tools

**Key finding: the parent-facing AI-IEP niche has independently converged on our two signature moves** — per-claim citation to IDEA/§504/state regs + "not legal advice" disclaimers. So "cite + not-advice" is **no longer a unique wedge inside K-12 IEP.**

- **Parent-facing, now citing law:** **IEP Desk** (iepdesk.com — "each rule shown with its citation"), **EveryIEP** (everyiep.com — "answers cite actual IDEA statutes… not guesses"; broadest life-scope incl. transition/adult-life), **IEP Advocate.ai** (cites IDEA + 50-state law + case precedent), **IEP Compass** ("Claudia"), **My IEP Hero** (weak citation + human-advocate marketplace). **All draft letters / give recommendations** — none holds a pure never-advise line, and all are K-12 IEP/504-bounded.
- **Teacher/school-facing content generators (opposite of us):** **MagicSchool AI**, **AbleSpace**, **Playground IEP**, and goal-generators (**Monsha, Lernico, Varsity Tutors, Progress Learning**) — generate IEP content, no per-claim regulatory citation.
- **Clinical / assistive:** **Parallel Learning** ($20M Series B Dec 2025; **diagnoses** dyslexia/ADHD), **Everway** (formerly Texthelp+n2y; assistive-tech + compliance), **Goally** (child life-skills app).

**Flags:** **Tract — unverifiable** in special-ed. **Prisms VR** is general STEM, not IEP. Several verified via store/snippet, not deep-fetch (directional).

---

## Bucket 5 — Disability-rights / self-advocacy information resources

These are the **content our corpus would cite/sit on**, and the players whose individualized-advice function we deliberately refer out to.

- **Dead/moved — stop citing as live:** **Disability.gov** (retired 2017). **Benefits.gov** now 301-redirects to USA.gov Benefit Finder.
- **Federal, PUBLIC DOMAIN → freely ingestible:** **ADA.gov** (+ ADA Info Line; **verified: no government ADA/IDEA chatbot exists** — a real interface gap), **USA.gov disability services**, **ACL.gov** (explicitly **aging AND disability**), **Eldercare Locator** (referral, aging), federal **medicaid.gov** waiver factsheets. **CPIR / parentcenterhub.org** ≈ ingestible with attribution per its own reuse terms (friendliest non-federal corpus).
- **Nonprofits/legal — COPYRIGHTED (permission needed) + they give individualized advice we must not:** **NDRN / the P&A system** and Michigan's **Disability Rights Michigan** (legal representation), **DREDF** (litigation), **The Arc** national + **Arc Michigan** (IDD-only), **Michigan Alliance for Families** (MI's PTI).
- **Michigan-deep:** **MDHHS** and **Michigan HCBS waivers** — Habilitation Supports Waiver (DD/ID) and **MI Choice** (aging + disability); **state content is NOT public domain — michigan.gov requires prior written permission to ingest.** **4AMI** (16 Area Agencies on Aging) and **Elder Law of Michigan** copyrighted.
- **211 / MI 211:** a **referral/routing layer** (who to call), complementary to our **answer/synthesis layer** (what the rule says) — a partner, not a scrape source.

---

## Bucket 6 — General AI health / benefits chat assistants

- **OpenEvidence (openevidence.com) — the key architectural analog.** Grounded RAG over a **curated peer-reviewed corpus with inline, traceable citations**; ~15M clinical consultations/month; **~$12B valuation, ~$100M ARR, $250M Series D**; ad-funded (pharma). **Same architecture as us (cite every claim, no free generation) but opposite audience/domain — clinician-only (credential-gated), clinical decision support.** Best proof point: *"the clinician-trusted equivalent already exists precisely because it cites; we bring that discipline to families and to benefits/accessibility."* (Vendor site 403s automated fetch; corroborated across third-party sources.)
- **Zero Project AI Assistant** (radiaite.com case study) — RAG, source-linked, **never-advise, disability domain, accessibility-aware.** Closest on posture/architecture — but corpus is disability-*inclusion policy*, audience policymakers/researchers, **no aging**, not dependency-aware, not entitlement discovery.
- **Nava / Imagine LA benefits chatbot** — grounded RAG with direct-quote citations over ~40 programs; **caseworker-facing, benefits-only, pilot-stage.**
- **Oklahoma "SoonerGuide"** — single-state, single-program Medicaid Q&A; grounding/citation not documented.
- **Advise/triage contrast cases:** **Ada Health**, **K Health** (symptom checkers — triage/advise); **Included Health "Dot"**; **UnitedHealthcare/Aetna** payer navigators (recommend, high PII).
- **DIY baseline:** **Perplexity/ChatGPT** — used for benefits Q&A but open-web, freely advise, "overwhelmingly wrong for insurance searches" per cited critiques — the low-reliability baseline a curated corpus displaces.

**Flags:** **"Hearth Health" — unverifiable** (Hearth = home-services receptionist). **USAFacts** has no benefits AI assistant.

---

## Synthesis

### (a) Is anyone doing our exact combination?
**No verified 2026 player combines all five pillars.** Every close player concedes at least two:
- **OpenEvidence** — perfect architecture, but clinician-only + clinical.
- **Code for America × Anthropic** and **Nava** — perfect posture (cite; "the decision stays with you"), but caseworker-facing + single-program.
- **Zero Project** — cite + never-advise + disability + accessibility, but policy-audience, no aging, no entitlement discovery.
- **Special Needs Navigator (Sage)** and parent-IEP tools (**IEP Desk, EveryIEP**) — educational/entitlement-adjacent, and (the IEP tools) cite law — but they **draft/advise**, don't cite (Sage), disability/K-12-only.
- **BenefitsCheckUp**, **TCARE** — span aging+disability, but estimate eligibility / aren't a cited knowledge layer.

### (b) Whitespace / differentiation (defensible)
1. **Strict never-advise + who-decides** is essentially **unoccupied on the consumer side** (only caseworker-facing Nava / CfA hold it).
2. **Cross-domain span (disability ∪ aging ∪ accessibility).** The funded AI leaders (**Chapter, Hera**) are **aging-only**; special-needs/IEP tools are **disability/child-only**. **Accessibility as a first-class axis is claimed by almost no one.**
3. **Citation-grounded RAG for consumers/families** — proven to build trust (OpenEvidence), not yet brought to a family/benefits audience.
4. **Dependency-aware/anticipatory** — only Benefit Kitchen's recert-loss prediction resembles it (and only for dollars).
5. **Non-clinical + low personal data** — the norm is high-PII human coordination or clinical delivery.
6. **Interface gap:** government rights content (ADA/IDEA) has **no conversational/AI interface at all.**

### (c) Crowding / risk (well-funded and close)
- **Aging navigation is heating up and well-capitalized:** **Chapter (~$3B, >$100M ARR)** and **Hera ($27M Series A, Medicare-reimbursed $0-to-family)**. If either broadens from Medicare into disability + adds citations, they close distance. "Conflict-free" is already weaponized (Chapter, Understood Care).
- **OpenEvidence ($12B)** could extend its cite-grounded engine toward consumers/benefits — the biggest architectural-adjacency risk.
- **Parent-IEP AI is crowded and already citing law** — our IEP surface is **not** blue ocean; differentiate on never-draft + broad adult-life scope.
- **Government AI is arriving** (state SNAP/Medicaid chatbots; CMS navigation on Medicare.gov; HHS/ACL "$2M Caregiver AI Prize", Nov 2025) — could commoditize single-program benefits Q&A from below.
- **findhelp** (TPG-backed) and **Undivided** are adjacent incumbents with reach.

### (d) Regulatory / trust angles — and the corpus-rights caveat (load-bearing for ADR-011)
- **Citation-as-trust** is validated by OpenEvidence and by **Nava's** explicit rationale (citing lets a human verify).
- **"Never adjudicate" as a design stance** is near-verbatim ours at **Code for America × Anthropic** and **Nava** — serious civic-tech treats non-adjudication as the safe/compliant posture.
- **Referral-fee conflict is a live regulatory wound** — the 2024 **Senate Special Committee on Aging** investigation of A Place for Mom — our no-recommendation/no-referral-fee model is a trust advantage (reinforces ADR-013).
- **Regulated-device boundary:** Cognoa/Canvas Dx (FDA) and symptom-checker classifications mark the clinical line our never-diagnose stance stays clear of.
- **Corpus-rights caveat (feeds ADR-011 rights tiering):** federal content (ADA.gov, USA.gov, ACL, medicaid.gov factsheets, CPIR-with-attribution) is ingestible; **all Michigan state content (MDHHS, michigan.gov waiver pages) and all nonprofit content (Arc, NDRN/DRM, DREDF, Michigan Alliance, 4AMI) are copyrighted and require permission.** This shapes what the rights-cleared corpus can actually contain — the first-version corpus will be **stronger on federal policy than on state-specific detail** until permissions are secured.

**One-line takeaway:** the exact intersection — consumer-facing, citation-grounded, strictly
never-advise, entitlement-*discovery* with who-decides, dependency-aware, spanning disability +
aging + accessibility, non-clinical — is **not occupied by any verified 2026 player**; the
pieces exist separately (OpenEvidence's architecture, CfA/Nava's non-adjudication posture,
Chapter/Hera's funded aging navigation, the now-citing parent-IEP tools), and the principal
risk is a well-funded aging-navigation leader or OpenEvidence broadening into the lane.

---

## Could-not-verify flags
- **"Wonder"** special-needs navigator — no current company found.
- **"ExplorerAI" / "Benji"** benefits screeners — unverifiable.
- **"Herald"** caregiving — does not exist; it is **Hera**.
- **"Hearth Health"** AI — unverifiable.
- **"Tract"** special-ed — unverifiable; **Prisms** is VR STEM, not IEP.
- **CareYaya "$690B NVIDIA acquisition"** — confirmed **hoax**.
- Vendor pages blocking automated fetch (OpenEvidence, MDHHS/michigan.gov) corroborated via independent third-party sources; self-reported scale/funding figures are directional, not audited.
