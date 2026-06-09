# Kathai Chithiram — கதை சித்திரம்

> *Kathai* (கதை, "story") → *Chithiram* (சித்திரம், "picture"). **Story to picture.**
> A parent's words go in; an animation a child can actually understand comes out.

## What this is

**Kathai Chithiram turns a personal story, written by a parent, into a short animation designed to be understood by a child with special needs.**

Children on the autism spectrum and with other developmental needs often comprehend a
situation far better when it is shown as a calm, predictable, visual narrative — the
principle behind *social stories* and visual schedules. Kathai Chithiram makes that
personal and on-demand: instead of a generic clip, a parent describes *their* child's
situation in their own words ("Silas is scared of brushing his teeth"), and the system
produces a gentle, paced, captioned animation that walks the child through it.

The name says the job: **a story, made into a picture.**

## The pattern

```
Parent writes a story  ──▶  generation (wegofwd-llm)  ──▶  structured scene script  ──▶  renderer  ──▶  animation (mp4)
   "in their words"          provider-agnostic LLM        scenes + narration + poses     stick-figure / Blender   the child watches
```

- **Generation seam — `wegofwd-llm`.** Scene breakdown, narration, and pacing are produced
  through the shared **`wegofwd-llm`** provider package (the same typed LLM seam Mentible
  consumes), so the story → scene-script step is provider-agnostic and reusable across the
  family. The LLM's job is to turn free-form parent text into a structured, child-appropriate
  scene script (clear steps, short sentences, predictable rhythm).
- **Rendering.** A scene script is rendered into a video. Two reference renderers exist today
  (see *Current state*); the rendering layer is intended to sit behind a stable scene-script
  contract so renderers can evolve without changing the generation step.

## Current state (prototype)

This repository currently holds the **proof-of-concept renderers** and the first hand-built
social story, *"Silas Shines His Smile"* — an 11-scene tooth-brushing routine:

| File | What it is |
|---|---|
| `generate_animation.py` | v1 renderer — matplotlib + imageio, stick figures, 24 fps → `silas_shines_his_smile.mp4` |
| `blender_animation.py` | v2 renderer — `blender --background --python`, Grease Pencil + compositor text cards, 11 scenes × 4 s ≈ 44 s → `silas_shines_his_smile_v2.mp4` |
| `silas_shines_his_smile.mp4` | rendered v1 |
| `silas_shines_his_smile_v2.mp4` | rendered v2 |

These were authored by hand — the scene scripts are written directly in Python. The product
work ahead is to **lift the scene script into a structured, generated artifact** (produced via
`wegofwd-llm` from a parent's story) and feed it to the renderers, so a parent never touches code.

## Roadmap (next)

1. **Scene-script schema** — define the structured artifact a renderer consumes (scenes, poses,
   narration, timing, accessibility hints).
2. **Generation step** — parent story → scene script via `wegofwd-llm`, with child-appropriate
   constraints (short sentences, one idea per scene, predictable pacing, calm palette).
3. **Renderer behind the contract** — make the Blender renderer consume the scene script rather
   than hard-coded poses.
4. **Parent-facing intake** — a simple way for a parent to submit a story and receive the animation.

## Family

Part of the WeGoFwd2020 portfolio (StudyBuddy OnDemand, Mentible, Pramana, Thittam). The name
is Tamil, alongside **Thittam**; the generation seam is the shared **`wegofwd-llm`** package.
