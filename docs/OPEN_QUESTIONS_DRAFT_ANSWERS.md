# Kathai Chithiram — draft answers to the eleven open questions

**Status:** Straw-man, not authored policy. **For:** the clinical collaborator to tear apart.

A note on what this document is and isn't. The system is deliberately built so that no
engineer and no AI sets a clinical number (ADR-003). This document does not break that rule.
None of the numbers below are policy. They are *starting positions* — drawn from published
practice literature and framed as options — so the person who does author the policy has
something concrete to react to instead of a blank field. Where a value is genuinely a
clinical judgement, it is marked **[clinician sets]** and left open.

Grounding for the story-craft answers is mainly Carol Gray's social-narrative work and the
broader visual-supports evidence base; grounding for the transition answers is US IDEA
structure. None of it substitutes for the named professional the plan requires.

---

## On how a story should speak to a child

### Q1 — Directive vs descriptive ratio

**Starting position:** at least **2 descriptive/perspective/affirmative sentences for every
1 directive sentence**, tunable upward toward 5:1. Default the enforced floor at 2:1.

This mirrors the long-standing social-narrative "ratio" idea: the story mostly *describes
what happens and what people feel and why*, and only sparingly *tells the child what to do*.
A story that is mostly instructions reads as a demand and tends to fail; the working
material is the description.

**Should it vary by child? Yes, plausibly:**
- Younger child / earlier comprehension → push toward more descriptive (higher ratio, fewer
  directives), because a directive assumes the child can hold and act on an instruction.
- Older child / concrete goal (a specific step they're learning) → a little more directive
  may be appropriate.

**What the software already does:** counts sentence functions and enforces the ratio. What
it needs is the number. **[clinician sets the floor, and whether it varies by profile.]**

### Q2 — How much text on screen

Technical limit is 140 characters/scene; the clinical limit should be much lower.

**Starting position:**
- **Pre-readers:** little or no on-screen text. Rely on the image and the narration. Text
  competes for attention it can't yet use.
- **Emerging/able readers:** one short sentence per scene, roughly **5–12 words**, one line,
  large type, matched to the child's reading level rather than age.

**Does it change with reading level / age?** With *reading level*, yes — directly. With age,
only insofar as age proxies for reading level, which it often doesn't for this population.
Suggest the policy key off a stated reading band, not age. **[clinician sets the bands.]**

### Q3 — Story length

Scenes are 2–8s; today there's no cap on scene count.

**Starting position:** cap total length, not just scene length. A social narrative works by
being watchable repeatedly before the event, so it must be short enough to rewatch without
friction. Suggest **6–12 scenes, total runtime under ~90 seconds** as an initial ceiling,
with a shorter default for younger children. **[clinician sets the cap and whether it scales
with profile.]**

### Q4 — What makes a well-intentioned story bad (the rejection taxonomy)

This is the highest-leverage answer, because every named failure that can be detected becomes
an automatic check — clinician time spent once, paid back on every future story. Draft list,
split by whether the software can plausibly catch it:

**Automatable (turn into validators):**
- **Too directive** — exceeds the directive ratio (Q1). *Already checkable.*
- **Second-person commands** — "You will stay calm," "You must not run." Detectable by
  sentence function + person.
- **Over-promising the outcome** — "You won't be scared," "It won't hurt." Guarantees the
  story can't keep. Detectable by a promise/negation-of-feeling pattern.
- **Negative framing** — story dwells on the problem rather than showing it going well.
  Partially detectable via sentiment/polarity per scene.
- **Text overload** — over the Q2 word limit. *Already checkable.*
- **Asserting the child's internal state as fact** — "You feel happy now." Detectable by
  second-person + feeling verb in declarative mood; softer forms ("sometimes children feel…")
  are fine.
- **No resolution** — story ends on the hard moment with no "and then it was okay." Detectable
  by requiring a closing reassuring/affirmative scene.

**Not automatable (needs the human review gate — but nameable, so reviewers are consistent):**
- **Wrong emotional register** — cheerful about something the child finds frightening;
  dismissive of a real difficulty.
- **Too abstract** — talks about concepts, not the concrete this-bathroom-this-toothbrush.
- **Wrong level of detail** — either skips the step that's actually hard, or overloads with
  detail that overwhelms.
- **Unrealistic tidiness** — everything always goes perfectly, which sets up failure when it
  doesn't. (Consider: is a "sometimes it's hard, and that's okay" beat *required*?)
- **Coercive/compliance-shaped** — frames the child's job as obeying, not as understanding.
- **Sensory mismatch** — narration or depiction that would itself be aversive to the child
  it's for.

Recommend the collaborator name and define each, mark which are hard-reject vs
soft-flag-for-review, and let engineering wire the automatable ones. **[clinician owns the
taxonomy and the reject/flag split.]**

---

## On what the animation should be able to show

### Q5 — The twenty things worth drawing next

Prioritised by how often they appear in the target situations (Q6) and how badly their
absence forces a refusal today. Grouped:

**Settings (highest value — these are where "blank room" bites):**
1. Shop / supermarket aisle + checkout
2. Car interior (travel, car seat)
3. Waiting room (medical/dental/clinic)
4. Dentist / doctor exam chair
5. Playground
6. Dining table / mealtime
7. Toilet / bathroom-with-toilet (distinct from the wash setting)
8. Hair salon / barber chair
9. Front door / hallway (arrivals, departures, drop-off)

**Expressions (currently four — the gaps that matter most):**
10. Scared / anxious
11. Overwhelmed
12. Proud
13. Calm/relieved (the "it went okay" face)

**Gestures (currently two):**
14. Pointing / requesting
15. Covering ears (sensory)
16. Hand up / "stop" / asking for a break
17. Taking a deep breath / self-regulation gesture

**Props / objects (the practical enablers):**
18. Visual schedule / first-then board (appears across nearly every situation)
19. Timer / visual countdown
20. Headphones or ear defenders

Honourable mentions if the budget stretches: toothbrush-already-exists check, weighted
blanket, seatbelt, shopping cart, food-on-plate variants, coat/shoes (dressing).

**[clinician re-orders by what actually comes up; this is a guess by frequency, not by
caseload.]**

### Q6 — Which situations first

The founder's list is good. Ranked by frequency × distress × how well a *pre-watched*
narrative helps (it helps most for **predictable, recurring, anticipatable** events):

1. **Transitions** (ending one activity, starting another) — most frequent, most generalisable.
2. **Hygiene** — teeth, bath, toilet, handwashing, haircut/nails.
3. **Mealtimes** — including new/refused foods.
4. **Waiting.**
5. **Unexpected change of plan** — the "today is different" story.
6. **Medical / dental visit** — high distress, highly anticipatable, big payoff.
7. **Sensory overwhelm** — and what to do about it (break, headphones).
8. **Asking for help / asking for a break.**

Additions worth considering: **separation / drop-off**, **bedtime**, **going to a new place**.

**[clinician confirms the ordering against real caseload.]**

---

## On the other audiences

### Q7 — Who is the "person learning to help", really

**Best fit for the first helper surface:** paraprofessionals / classroom aides,
direct-support professionals (DSPs) in disability services, respite workers, substitute staff,
and new kinship carers (a grandparent suddenly doing daily care). Common thread: **high
turnover, thrown into situations with little durable training, and — crucially — they already
know the specific child; what they lack is the general frame.**

**What they most need that they don't have** (and that a cited corpus can lawfully give):
- **The "why" behind behaviour** — that behaviour is communication and usually serves a
  function (escape, access, sensory, attention). This single frame changes how someone
  responds.
- **Antecedent strategies** — what to change *before* the hard moment, not how to react after.
- **What *not* to do** — the common well-meaning responses that make things worse.
- **De-escalation basics** and knowing the edge of their role — when to get the professional.

What they explicitly must *not* get from the tool: anything specific to their particular
child (that's the "never advise" line), or crisis handling (that's Q9).

### Q8 — What actually changes at each transition (the cliffs)

Under US IDEA, the genuine cliffs — where entitlement or system changes abruptly rather than
gradually:

- **Age 3** — Early Intervention (IDEA Part C) ends; preschool special education (Part B)
  begins. Different agency, different rules, families often fall through the seam.
- **Preschool → Kindergarten** — services and staffing change; less individualised.
- **Around age 14** — transition planning must appear in the IEP (some states 16). Families
  often don't know to push for it.
- **Age of majority (18 in most states)** — educational rights transfer to the young person
  unless guardianship/supported-decision-making is arranged in advance. Blindsides families.
- **School exit (18–22, when the student ages out) — the sharpest cliff by far.** IDEA is an
  *entitlement*; adult services (Medicaid waivers, vocational rehab, day programs) are
  *eligibility-based and waitlisted*, often years long. The support that was guaranteed simply
  stops, and the replacement must be applied and qualified for.

**What families most wish they'd known a year earlier:** apply for adult-services waivers
*long* before school exit (waitlists); decide the guardianship/decision-making question before
18; that transition planning is a right they can demand at the IEP table.

This is exactly the "lifespan navigator" audience (P3), and the 18–22 exit is where a cited,
current corpus would earn its keep. **[clinician/collaborator confirms which cliffs to build
first; law varies by state — Michigan first per ADR-009.]**

### Q9 — Self-injury / crisis routing (the one to get right)

**Firm design stance, for the collaborator and counsel to ratify — not to invent from
scratch:**

The tool **must not advise** on a specific child in crisis, and must not attempt to judge risk
itself (ADR-001: automation is never the sole safeguard). When crisis language is detected,
it should **stop answering the question, say plainly that it can't advise on a specific
person, and route to a human** — immediately and unmissably.

Draft of what it routes to (US; **counsel + clinician must confirm exact wording and
numbers**):
- **Immediate danger to life:** call emergency services (911).
- **Mental-health crisis:** 988 Suicide & Crisis Lifeline (call or text 988).
- **Text option:** Crisis Text Line (text HOME to 741741).
- **The child's own team:** their clinician / behaviour specialist / school team — named as the
  right people for anything specific to this child.
- **For ongoing self-injurious behaviour** (not immediate danger): name that the path is a
  functional behaviour assessment by a qualified professional, and route there — without
  suggesting what to do in the moment.

**What it must never do:** offer a technique to try on the child, minimise ("it's probably
fine"), or continue as if it were a corpus question. This path is a **precondition** — nothing
that can receive such a message ships until this route exists and a professional has authored
the words. **[clinician + counsel author and sign off the exact copy.]**

---

## As a sounding board

### Q10 — Would you have used this?

This is the founder's to answer from lived experience, not mine to invent. The honest
reframing to put to the collaborator: the effort of writing the story down is the tax, and the
question is whether it's paid *once per situation and reused* (worth it) or *per episode*
(probably not). The design should make the first story for a situation the only expensive one —
templates, reuse, editing an existing story rather than authoring fresh. If writing it down is
a one-time cost that produces a film watchable for weeks, the effort likely clears. If every
bad evening needs a new story, it won't. That's a product-shape question the collaborator's
experience can answer better than any argument.

### Q11 — Is the second product a distraction? (Argue him out of it)

He asked to be argued out, so here is the counter-case made properly:

**Yes — the *assistant surface* is a distraction; the *corpus* is not.** Separate the two.

- **One person, two products, is the stated top risk** — and the second product is the one with
  no human gate. The story-maker is safe because a human reviews every output before a child
  sees it. The assistant is read by an adult who may act immediately, with no gate. That is a
  categorically harder safety problem, and it's the one being added while the *first* product
  still hasn't shipped.
- **"Never advise" refuses the most valuable question** ("does my child qualify?"), by the
  founder's own admission. A product whose best question is the one it must decline has an
  unproven core value proposition.
- **The crisis path (Q9) is unsolved and is a precondition.** Until it's built and
  professionally authored, the assistant cannot ship at all — so building the rest of it now is
  building toward a gate that isn't open.
- **The corpus is unbounded scope.** Rights review, freshness, supersession, retraction
  tracking — it's a standing maintenance burden, not a build-once asset.
- **The same scarce clinician gates both.** Every hour on the assistant is an hour not spent
  getting the story product over its own clinical line.

**But** — and this is why "kill the corpus" would be wrong — the corpus *also* grounds the
story generator (KC-21), which is squarely the first product. So the defensible plan is the
one already written: **build a thin corpus scoped only to grounding story generation, and
defer every assistant surface** behind the clinician gate and the crisis path. That keeps the
asset that helps the product he's shipping, and drops the second product until the first one is
actually in children's hands.

In short: he's right to build the corpus, right to be suspicious of the assistant, and the
existing kill criterion (stop and finish the story product if it's not shipped when KC-21 is
done) is the correct guardrail. Hold him to it.
