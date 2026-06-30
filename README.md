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

Those two were authored by hand — the scene scripts were written directly in Python. The product
work since has **lifted the scene script into a structured, generated artifact** (produced via
`wegofwd-llm` from a parent's story) and fed it to the renderers, so a parent never touches code.

## Roadmap

All four foundational steps are built and on `main`:

1. ✅ **Scene-script schema** — the structured contract a renderer consumes (`scene_script/`:
   schema + validation; scenes, narration, timing, safety, accessibility).
2. ✅ **Generation step** — parent story → validated scene script via the `wegofwd-llm` seam,
   with a concrete provider and a validate-and-repair loop (`generation/`).
3. ✅ **Renderer behind the contract** — the reference renderers consume the scene script instead
   of hard-coded poses (`rendering/`).
4. ✅ **Parent-facing intake** — `kc intake` walks a parent through consent → story → a
   review-gated draft (`intake/`).

End to end, `kc intake` / `kc generate` take a parent's story to a captioned draft animation,
with privacy (the name is stripped before the provider, scene scripts hold only a token, consent
is captured) and a human-review gate enforced in code.

**Next, beyond the foundation:** M1 per-child progress quantification — the capture-track
primitives are built (`feedback/`; ADR-002 *Accepted*), but the progress **engine** and
therapist-suggested premise customization stay **gated** behind ADR-002's preconditions
(professional collaborator, tested therapist-in-the-loop path, DPIA). Plus production hardening:
encryption-at-rest, a no-training / zero-retention provider key, and a delivery/review workflow.

## Family

Part of the WeGoFwd2020 portfolio (StudyBuddy OnDemand, Mentible, Pramana, Thittam). The name
is Tamil, alongside **Thittam**; the generation seam is the shared **`wegofwd-llm`** package.
