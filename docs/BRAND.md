# Kathai Chithiram — Brand & Visual System

**Status:** Draft v0.1 (2026-06-13)

The name is Tamil: *Kathai* (கதை, "story") → *Chithiram* (சித்திரம், "picture").
Everything in this system serves one job — **a story, made into a picture a child
can understand** — and one audience constraint: the primary UI is used by children
with special needs, so calm, predictable, and concrete beat clever every time.

---

## 1. Design laws (non-negotiable)

These are not guidelines; they are enforced like the content-safety rules in
[`CONTENT_SAFETY.md`](CONTENT_SAFETY.md).

1. **Concrete, never abstract.** A literal-minded child reads a picture of the real
   thing. "Watch" is a screen; "done" is a tick; "home" is a house. No metaphor icons.
2. **Icon + word + read-aloud, always together.** Never icon-alone on a child surface.
   Every action carries its symbol, its plain-language label, and tap-to-hear audio.
   Redundancy is the accessibility (and AAC) mechanism.
3. **No red, no alarm.** "Off" states and "no" use a calm slate (`#8A8A82` / `#A8AEB4`),
   never red, never a harsh "X". Frame everything as *what to do* ("take a break",
   "later"), per Content Rule #1/#3.
4. **Large targets, calm motion.** Big tap zones; slow, reduced-motion-friendly
   transitions; nothing flashing (seizure-safety ≤ 3 Hz, as in the scene-script contract).
5. **One consistent style.** Same rounded stroke, same weight, same palette across the
   whole set — because predictability *is* the therapeutic mechanism.

---

## 2. Palette

Low-saturation, AA-legible, extended from the renderer palette so brand and generated
output match. Lead with blue + green; amber is a sparing accent; **red is intentionally absent.**

| Role | Hex |
|---|---|
| Paper (surface) | `#F5F1E8` |
| Calm blue · primary | `#4A90D9` |
| Soft sky | `#AED6F1` |
| Reassuring green | `#5DBB63` |
| Soft green (fills) | `#9FD4A0` |
| Warm amber · sparing | `#F2C14E` |
| Ink (text/line) | `#2E2E2E` |
| Warm skin (illustration) | `#EFC29A` |
| Calm slate (off / no) | `#8A8A82` · `#A8AEB4` |

## 3. Typography

**Baloo superfamily** — one rounded, friendly personality across Tamil and Latin, so
கதை சித்திரம் and "Kathai Chithiram" share DNA in any bilingual lockup.

- Tamil: **Baloo Thambi 2** · Latin: **Baloo 2**
- Alternates with good Tamil + Latin coverage: Mukta Malar, Hind Madurai, Noto Sans Tamil.
- Two weights only (regular 400, medium 500). Generous spacing; sentence case.

## 4. Logomark

Three explored directions; **selection pending** (no logo asset committed yet):

- **Kolam loop** *(recommended)* — a calm, repeating, predictable looping motif rooted in
  Tamil kolam; the mark *means* the product. Distinctive and abstract enough to never read
  as a face.
- **Spoken frame** — a speech bubble that is also a picture (best at teaching the name).
- **Open story** — a book whose page becomes a screen (clear but generic).

## 5. Characters

Two original child characters in the spirit of R.K. Laxman's ink line-art (the trademarked
"Common Man" is **not** reproduced). Warm, gentle, inclusive; usable as friendly guides and
as stand-ins in story thumbnails. **No photographs of real children, ever** (privacy +
universality).

| Asset | File |
|---|---|
| Boy + girl, colour | [`assets/brand/characters_boy_girl_color.svg`](../assets/brand/characters_boy_girl_color.svg) |
| Boy + girl, ink (master) | [`assets/brand/characters_boy_girl_ink.svg`](../assets/brand/characters_boy_girl_ink.svg) |

The **ink version is the reproducible master**; the colour version is a tint of it.

## 6. Child action icons

The interface vocabulary. All live in [`assets/brand/icons/child/`](../assets/brand/icons/child/),
each a standalone 48×48 SVG (the feelings picker is 132×48). Every icon must be shown with
its label and read-aloud audio (Law #2).

### Stories
| Action | File |
|---|---|
| my stories | `my-stories.svg` |
| watch | `watch.svg` |
| watch again | `watch-again.svg` |
| listen | `listen.svg` |
| words (captions) | `words.svg` |
| pause | `pause.svg` |
| next | `next.svg` |
| sound on / off | `sound-on.svg` · `sound-off.svg` |
| words on / off | `words-on.svg` · `words-off.svg` |

### My day (planner)
| Action | File |
|---|---|
| my day | `my-day.svg` |
| how long (timer) | `how-long.svg` |
| first, then | `first-then.svg` |
| choose | `choose.svg` |
| take a break | `take-a-break.svg` |
| later | `later.svg` |

### Done & feelings
| Action | File |
|---|---|
| all done | `all-done.svg` |
| well done | `well-done.svg` |
| how I feel (calm / okay / upset) | `how-i-feel.svg` |
| yes / no | `yes.svg` · `no.svg` |
| my stars (token board) | `my-stars.svg` |
| my prize | `my-prize.svg` |

### Getting around
| Action | File |
|---|---|
| ask a grown-up | `ask-a-grown-up.svg` |
| home | `home.svg` |
| go back | `go-back.svg` |

## 7. Open decisions

- **ARASAAC alignment.** Plan an optional symbol layer aligned to ARASAAC — the
  open-license (Creative Commons) AAC pictogram set many of these children already use at
  school and in therapy. Our house icons are the friendly default; an ARASAAC toggle speaks
  a vocabulary the child has already learned.
- **Adult icon language.** Parent/therapist surfaces (literate adults: author, share,
  caseload, review, add-to-plan, track) get a deliberately *distinct, lighter* icon
  treatment — not the child set. To be designed separately.
