# Kathai Chithiram — what it is, where it stands, and what I need your help deciding

**Written:** 10 September 2026 · **For:** review and collaboration
**Name:** Tamil — *kathai* (கதை, story) + *chithiram* (சித்திரம், picture)

---

## Read this first

This is a briefing, not a pitch. It describes something that mostly works, a set of
decisions I've written down, and a set of choices I've deliberately **refused to make on my
own** because they aren't mine to make.

That last part is the reason I want you in this. There are numbers in this system that
decide how a story speaks to a child — how much it tells them what to do, how many words go
on screen, how long a scene lasts. I've built the machinery so that a person sets those
numbers and the software just carries them out. I have not set them, and I don't intend to.

There's a real question near the end about whether you should be the person who signs off on
this work or the person who does it — those may need to be different people, for reasons
that have nothing to do with competence. I'd rather raise it now than discover it later.

You can read this in about half an hour. The questions are in section 8.

---

## 1. What it does

A parent writes, in their own words, about something their child is finding hard.

> *"Silas hates having his teeth brushed. He runs away when he sees the toothbrush and it
> turns into a fight every single night."*

The system turns that into a short, calm, captioned animation — a handful of slow scenes,
narrated gently, that walks the child through what happens and shows it going well. The
child watches it before the thing happens, and again, and again.

That's it. One parent, one situation, one small film made for one child.

It rests on an old and well-supported idea: many children on the autism spectrum, and many
with other developmental needs, do much better with a situation they've already seen laid
out concretely and predictably than with the same situation explained in the moment. Visual
schedules and social narratives work on exactly this principle. What's usually missing is
that the available materials are *generic* — a story about a generic child brushing generic
teeth — and the thing that makes them work is that they're about **this** child, in **this**
bathroom, with **this** routine.

Making one properly takes a parent or a therapist real time and some skill. That's the gap.

---

## 2. What actually exists right now

More than you might expect. This isn't a proposal — it's a working system.

A parent's story goes through this pipeline today:

1. **Intake.** Consent is captured first — that the person is the guardian, that they
   understand the text goes to an AI service, that they know a human reviews it before the
   child sees anything. Nothing is generated or stored until all three are given.
2. **The name comes out.** Before a single word leaves the machine, the child's name and
   nickname are replaced with a placeholder. The real name is put back only at the very last
   moment, when the video is drawn. It is never in stored files and never in logs. If the
   replacement fails for any reason, the whole thing stops rather than proceeding.
3. **The story is turned into a "scene script"** — a strict, structured description of each
   scene: what's said, what's shown, how long it lasts, how it fades in and out.
4. **The scene script is checked against rules** before anything is drawn. Scenes must be
   between two and eight seconds. Captions must match the narration word for word. No
   flashing transitions. If it fails, it's rejected — never quietly fixed up.
5. **It's drawn into a video**, with narration, gentle sound and captions.
6. **The video is measured for safety** — flash rate, harsh contrast changes, audio levels.
   If it fails, the draft is deleted rather than kept.
7. **A human reviews it** and approves or rejects it. Nothing reaches a child otherwise.
   Anything not approved is automatically deleted after thirty days.

Everything is encrypted on disk. Deletion is real deletion, verified by a test — including
from backups. A person with system access can't browse a family's story without an explicit
relationship to it, and every access attempt is logged.

There are 641 automated tests. There is a privacy notice written for parents in plain
language, and a formal privacy impact assessment.

**What's holding it back from launch is not code.** It's three things, and all three need a
person: a professional to review the clinical side, a data-protection sign-off, and some
operational setup. I ran out of engineering excuses a while ago.

---

## 3. The problem I hit, and what I want to do about it

The animation quality has a ceiling, and it's lower than I realised.

The system can draw **six settings** (bathroom, bedroom, kitchen, classroom, outdoors, and a
neutral calm room), **four facial expressions**, **two gestures** (waving, and arms at rest),
and about **nineteen objects**.

That list is written down nowhere the AI can see. So if a parent's story is about the
supermarket, the AI cheerfully asks for a supermarket, every check passes — and the child
watches a figure standing in a blank room. Nothing anywhere reports that this happened.

This turns out to be the single biggest quality problem in the product, and it needs no AI
at all to fix. It needs someone to write down what the system can draw, make asking for
anything else an error, and then **decide what to draw next** — which is a question for
someone who knows what situations actually come up.

Alongside that, I want to stop renting a general-purpose AI and run our own. Four reasons,
and they're not equally strong:

- **Privacy** is the real one. Today a child's story is sent to another company. They've
  committed not to train on it or keep it, but that's a promise I can't verify from here.
  Running our own model on our own hardware means the story never leaves. That's a change in
  kind, not degree.
- **It would be ours.** A model plus the clinical thinking behind it is an asset, not a
  rented service.
- **Cost**, eventually — but honestly not for a long time. At our size it's cents per story.
- **Quality** — the general model is fine, but it doesn't know this domain in any deep way.

---

## 4. The bigger idea, and what it turned into

The more I looked at it, the more the story generator looked like the wrong size of ambition.

Three other groups of people need something here, and none of them wants a cartoon:

- **People learning to help** — classroom aides, direct-support workers, volunteers,
  trainees, grandparents. High turnover, very little durable training, constantly thrown
  into situations nobody prepared them for.
- **People whose needs keep changing.** This is the one I keep coming back to. A person's
  needs at six, at twelve, at nineteen and at thirty are not the same needs, and the adults
  around them have to keep re-learning — most sharply when school-based entitlements end and
  adult services begin, which in most places is a cliff rather than a step.
- **People building things** — practitioners designing programmes, people making assistive
  devices.

They all want the same thing: **an answer**.

That's a genuinely different machine from the one that makes cartoons. A cartoon is checked
by a human before a child sees it. An answer is read by an adult who may act on it
immediately. If it's wrong, there's no gate.

So the conclusion I came to is this:

> **Kathai Chithiram isn't too small. It's one surface on something that doesn't exist yet.**

The thing that doesn't exist is a properly curated, properly sourced, always-current body of
practice knowledge. The cartoon maker draws on it to write better stories. The answering
service draws on it to answer questions. **The knowledge is the asset. The products are
replaceable.**

And that reframe made the sequencing obvious: build the knowledge base first. It's the one
part that needs no clinician sign-off to *begin*, costs almost nothing, and makes the
product I already have better while I'm building it.

---

## 5. The rules I've committed to in writing

These are decided and recorded, not aspirations. I'd like you to push on any of them.

**The system never pretends to be a clinician.** No diagnoses, no medical claims, no
therapeutic promises. It never tells anyone what to do about a specific person and never
decides who qualifies for a service. It explains, it cites where the explanation comes
from, and it says who to ask next. If it can't cite something, it doesn't say it.

**Automation is never the only safeguard.** No version of this system decides whether a
child is at risk. It can notice and route to a person; it never judges.

**A child's story is never training data.** Ever, in any form — not anonymised, not
paraphrased. A model doesn't forget when a family asks to be deleted, and that single fact
settles it permanently.

**A child's mood is never something the software is trying to improve.** The system records
a simple session check-in — refused, prompted, or independent; did they finish; roughly how
it went. It would be technically easy to make the AI optimise for raising those numbers. That
would be a machine quietly learning to make a child *look* like they're doing better, and
it's forbidden.

**No engineer picks a clinical number.** There is no default anywhere in the progress code —
no default number of sessions, no default threshold. If nobody has authored a policy, the
system computes nothing. It's built so that a developer's guess cannot reach a child by
accident.

**Never scrape parent forums or social media.** People post about their children there. It's
health information about identifiable people, often children, who never agreed to any of
this. Not a close call.

**The human review gate doesn't relax** because the AI gets better.

---

## 6. What happens next, and what it costs

Two pieces of work. They don't compete, which is the useful part — one is waiting on a
person's time, the other on mine.

### The knowledge base — start now, roughly $4–10k

Gathering and organising the source material. Almost all of it is my own time; the only real
money is one bounded legal review of what we're allowed to use, which is genuinely tricky.
Two traps caught me out:

- **"Free to read" isn't "free to use."** Several of the best-known sources in this field
  are freely readable and permit no reuse at all.
- **"Government funded" isn't "government written."** Federal government *employees'* work is
  public domain; a university that received a federal *grant* keeps its own copyright. That
  turns out to matter enormously, because the single most useful set of practical how-to
  materials in this field is university-produced with no licence stated anywhere — and
  silence isn't permission.

What we *can* use is still substantial: federal health and education material, the national
parent-information centres (plain-language and explicitly public domain — the best thing of
its kind I found), state law, and a filtered slice of the open-access research literature.

Rough timeline: four to five months of evenings, at which point the story product itself
gets better because of it.

### The AI model work — later, roughly $17–28k

**Over 80% of that is a clinician's time, not computers.** The actual training runs cost a
few hundred dollars. What costs money is roughly a hundred hours of professional time:
designing the rubric, designing the range of situations, and then reviewing perhaps a
thousand generated stories one at a time and marking each accept, edit, or reject.

That is the whole budget, essentially. Which changes how I think about the plan: spend those
hours where they compound, and never on anything software can check.

Seven to nine months, and it can't start until there's a professional involved.

**I've written a hard stop into the plan:** if the story product hasn't shipped by the time
the knowledge base work reaches its fourth phase, I stop and finish the story product. The
most likely way this fails is that I build two interesting things and ship neither.

---

## 7. What could go wrong

Being straight about this, because you'll spot things I've talked myself past.

- **I'm one person building two things.** The plan has kill criteria for exactly this reason
  and I'd like you to hold me to them.
- **The most useful practical material is the material we can't use.** The workaround — cite
  it as a pointer, write our own text from the underlying research — is legitimate but it's
  real work, and the first version will be stronger on policy and research than on
  step-by-step practice.
- **Invented practice stories will be too tidy.** For training we have to invent parent
  messages, and invented ones are cleaner and better-organised than what a real parent writes
  at eleven at night after a bad evening. A system trained on tidy inputs may fall over on
  real ones.
- **The "never advise" line will frustrate people.** The most valuable question a parent asks
  is "does my child qualify for this?" — and that's exactly the one the system must refuse.
  Refusing it *well* is a design problem I haven't solved.
- **Someone will type something serious into the box.** A volunteer will ask what to do when
  a child is hurting themselves. That's not a question about research and it's the thing I
  most need to get right before any of this reaches a stranger.
- **A closed list of drawable things means honest failure instead of a wrong picture.** I
  think that's right. It also means some parents' stories get refused where today they'd
  quietly get something wrong. Tell me if you think that trade is wrong.

---

## 8. Where your judgement decides, not mine

These are real open questions. Each one is currently blank in the system, on purpose.

**On how a story should speak to a child**

1. **How much should a story tell a child what to do, versus describe what happens?** The
   literature talks about a ratio. The software counts and enforces it; the number is
   deliberately unset. What should it be, and should it vary by child?
2. **How much text on screen?** The technical limit is 140 characters per scene. What's the
   right *clinical* limit, and does it change with reading level or age?
3. **How long should a story be?** Currently 2–8 seconds a scene, no cap on scenes.
4. **What makes a well-intentioned story bad?** This one is the most valuable thing you could
   give me. If I have a list of the specific ways these go wrong — too abstract, too
   directive, wrong emotional register, wrong level of detail — I can turn most of them into
   automatic checks, and every one I automate is professional time I don't have to spend.

**On what the animation should be able to show**

5. **What are the twenty things worth drawing next?** Right now: six settings, four
   expressions, two gestures, nineteen objects. Adding to it is straightforward work — I just
   don't know what matters. What situations come up over and over that we simply cannot
   depict?
6. **Which situations should the system be good at first?** Hygiene, transitions, mealtimes,
   waiting, an unexpected change of plan, a medical or dental visit, sensory overwhelm,
   asking for help — that's my guess and it's only a guess.

**On the other audiences**

7. **Who is the "person learning to help", really?** I've been imagining aides, support
   workers and volunteers. Is that right? What do they not know that they most need to?
8. **What actually changes at each transition?** Which age points are genuine cliffs rather
   than gradual shifts, and what do families most wish they'd known a year earlier?
9. **What should happen when someone asks about self-injury or a crisis?** The system must
   route to a person. Who, and what should it say while it does? This is the one I least want
   to get wrong.

**As a sounding board**

10. **Would you have used this?** When it would have helped most, would a small film made
    from your own words have been worth the effort of writing them down — or is the effort the
    thing that kills it?
11. **Is the second product a distraction?** I've argued myself into it. Argue me out.

---

## 9. Where you could actually own the work

Not "give input on" — own, with your name on it.

| Piece | What it is | Why it's yours |
|---|---|---|
| **The narrative policy** | The file holding the ratio, reading load and story length | Software refuses to have defaults here; it's blank until a person fills it |
| **The rejection taxonomy** | The named list of ways a story goes wrong | Becomes automatic checks, so it pays for itself repeatedly |
| **The situation and profile grid** | Which situations, for which kinds of children | Defines what the system will and won't be good at |
| **Story review** | Marking generated stories accept / edit / reject | The largest single block of work in the plan |
| **The drawing wish-list** | What to add to the animation, in priority order | Turns an open-ended aspiration into a finite backlog |
| **Source curation** | Which material belongs in the knowledge base, and what's missing | Needs someone who knows what practitioners actually reach for |
| **The crisis routing** | Who to route to, and what to say | Safety-critical, and not a software question |
| **Parent-facing words** | Everything a parent reads | Currently written by me, which is the wrong person |

---

## 10. One awkward thing I should say plainly

Several of the documents behind this require a **named professional** who reviews the
clinical side — not as a courtesy at the end, but as a co-author. It's written in as a
precondition, and it's the main thing blocking two whole tracks of work.

You could do that work better than most people I could hire. But there's a separate question
underneath it: **the record needs to show that someone independent looked at this.** When a
data-protection officer, a school district or a funder asks who reviewed the clinical
judgement in this system, "the founder's spouse" is a weak answer regardless of
qualifications — not because the judgement is worse, but because independence is part of
what makes a review mean anything.

So I think the honest structure is: **you author, and a second professional reviews and is
named.** That's not a demotion — authoring is the harder and more interesting half, and it's
where nearly all the hours are. Reviewing needs far fewer, which also makes it much cheaper
to find someone for.

If you disagree with that reasoning, say so — I've thought about it for an afternoon, not a
career.

---

## 11. A short glossary

- **ADR** — Architecture Decision Record. A short document capturing one significant decision,
  why it was made, and what was rejected. Written once, never rewritten; if the decision
  changes, a new one supersedes it. There are twelve. `docs/ADR_INDEX.md` summarises all of
  them in plain language.
- **Scene script** — the structured description of a story, sitting between the AI and the
  animation. The AI writes one; the drawing code reads it. Neither talks to the other
  directly, which is what makes each testable.
- **Gated** — built, but deliberately switched off behind named conditions. Several parts of
  the system are complete and inert on purpose.
- **Corpus** — the curated body of source material the system draws on.
- **Retrieval** — looking something up and answering from what was found, rather than from
  what the AI remembers. The difference matters: you can check, correct and withdraw a
  looked-up fact, and you can't do any of those to a memory.
- **Fine-tuning** — adjusting an existing AI model on examples so it gets better at one
  specific job. Cheap and quick; the model is not built from scratch.
- **Zero data retention** — a commitment by an AI provider not to keep or learn from what's
  sent. Ours is configured that way. The point of running our own model is not having to take
  that on trust.

---

## Where to read further

- **`docs/ADR_INDEX.md`** — all twelve decisions, in plain language, with what's waiting on a
  person. Read this next.
- **`docs/LLM_PROGRAM_PLAN.md`** — the AI model plan: phases, costs, and the points at which
  I've committed to stopping.
- **`docs/KNOWLEDGE_BASE_PLAN.md`** — the knowledge base plan.
- **`PRIVACY.md`** and **`docs/PARENT_PRIVACY_NOTICE.md`** — what we hold and what we promise
  a parent. The second is deliberately written in plain language and I'd value your read of
  whether it succeeds.
- **`docs/CONTENT_SAFETY.md`** — the rules a story must follow. This is the most directly
  clinical document in the repository and the one most in need of a real review.
