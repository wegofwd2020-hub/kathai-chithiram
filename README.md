<p align="center">
  <img src="assets/logo.png" alt="Kathai Chithiram" width="460">
</p>

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

## Current state (single-operator prototype, full pipeline)

The end-to-end pipeline below is **built and green** (story → generation/authoring → validated
scene script → render, with privacy, safety, and a human-review gate enforced in code). The two
**reference renderers** and the first hand-built social story, *"Silas Shines His Smile"* (an
11-scene tooth-brushing routine), remain the render layer:

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

### Foundation — all four steps built and on `main`

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

#### Try it yourself — story → video, offline (no API key)

`--offline` generates the scene script locally by sentence segmentation — no LLM, no network, no
key — so you can feed any story and watch the video render. It does **not** adapt or safety-rephrase
the text (that's the LLM path); the name is still stripped and the human-review gate still applies.

```bash
kc generate story.txt --child-name Silas --offline --out video.mp4 --captions srt
```

Writes a playable `video.mp4` (with `video.srt` captions) alongside the sealed store copy.

#### Or author from a template — no prose, no key

`kc author` builds the story from a structured template (a title + ordered steps) instead of
free text, and lowers it deterministically to the same scene script. Pass a JSON file, or omit
it to be prompted interactively (see `docs/STORY_TEMPLATE.md`):

```bash
kc author story.json --child-name Silas --out video.mp4 --captions srt
kc author --child-name Silas --out video.mp4        # guided prompts, no file
```

#### The render options (all in-process, no data leaves the machine)

Every make-a-story command takes the same render flags: `--out` (a playable copy), `--captions
srt|vtt` (a sidecar), `--voice '<cli-tts> {out} {text}'` (narration), `--character-voice
ID=<cli-tts>` (a distinct voice per character), `--sfx ./sounds` (a local sound bank). Scenes
render with content-aware art (setting, backdrop, props, pose/expression) and gentle
fade/dissolve transitions, all under render-time seizure/flash + gentle-audio safety guards.

#### Commands

| Command | What it does |
|---|---|
| `kc intake` | Interactive parent flow: consent → name → story → review-gated draft. |
| `kc generate <story>` | Non-interactive from a file/stdin (`--offline` = no LLM/key). |
| `kc author [<template>]` | Author from a template file, or interactively; no LLM/key. |
| `kc review <id> --show\|--approve\|--reject` | The human review gate (KC-7). |
| `kc assign <id> --principal … --role reviewer\|therapist` | Grant a role (owner-only). |
| `kc progress <goal> --policy <file> --story <id>` | Run the M1 engine against a policy (gated; see below). |
| `kc suggestions <id>` | List a story's open premise suggestions (therapist). |
| `kc decide <id> <sug> --accept\|--edit\|--dismiss` | Therapist records a decision on a suggestion. |
| `kc family-create` / `kc child-add` / `kc therapist-add` | Onboard a family / child (age band only) / therapist (ADR-005 b). |
| `kc assign-child` / `kc consent` | Assign a therapist to a child; record parental consent (the lawful basis). |
| `kc program-create` | Establish a therapist's program (a set of goals) for a child (ADR-005 c). |
| `kc erase-child` / `kc erase-family` | Cascade right-to-erasure: hard-delete a child/family + all their stories. |
| `kc delete <id>` | Owner-only verifiable hard-delete + crypto-shred (right-to-erasure). |
| `kc retention-sweep [--dry-run]` | Purge undelivered stories past the retention window (ops). |

### Production hardening — built and on `main`

All five hardening tickets are implemented (`TICKETS/KC-5`…`KC-9`):

- ✅ **Encryption at rest** (KC-5) — AES-256-GCM for every stored artifact, keyed by
  `KC_STORAGE_KEY` (`storage/crypto.py`); reads/writes stay plaintext, ciphertext never crosses
  the store boundary.
- ✅ **Zero-retention / no-training provider key** (KC-6) — a dedicated `ANTHROPIC_ZDR_API_KEY`
  that **fails closed**; a child's story text never goes out on a general developer key.
- ✅ **Review → approve → deliver workflow** (KC-7) — `kc review` records an explicit human
  accept / reject; nothing is marked delivered without it.
- ✅ **Parent-facing privacy notice** (KC-8) — a plain-language notice shown *before* consent, with
  the notice version recorded against each consent (`docs/PARENT_PRIVACY_NOTICE.md`).
- ✅ **DPIA** (KC-9) — a Data Protection Impact Assessment whose risk register maps to the controls
  above (`docs/DPIA.md`; draft, pending DPO/counsel sign-off).

What remains before an EU/UK launch is **operational, not code**: DPO/counsel sign-off, confirming
the ZDR organization, and secret-manager key management.

### M1 — per-child progress → therapist-suggested premises (engine **gated**)

- ✅ **Capture track** — fixed, minimal feedback primitives per session (`feedback/`; ADR-002
  *Accepted*), keyed to a therapist-owned goal.
- ✅ **Engine-track scaffolding (inert)** — a read-only *evidence view* over the raw captured
  primitives and the therapist *accept / edit / dismiss* review plumbing (`progress/`). By design it
  computes **no progress measure** and **generates no suggestion**.
- ✅ **Engine mechanics (built, gated off)** — ADR-003 designs the engine as a deterministic,
  policy-driven interpreter, and its mechanics now exist (`progress/policy.py`, `progress/engine.py`):
  a `ProgressPolicy` **schema** plus pure `measure` / `suggest` functions over the evidence view.
  Every clinical parameter (window K, thresholds, trends, per-goal on/off) is collaborator-authored
  **configuration** — the code ships **no thresholds and no defaults**, so it cannot run until a
  policy is supplied.
- ✅ **Wire-up (built, gated by config)** — the policy loader, the runner (`measure` → `suggest` →
  record), and `kc progress <goal> --policy <file> --story <id>` are landed. But **no policy ships**:
  `--policy` is required, and recording a suggestion needs the therapist role (fails closed), so the
  engine literally does nothing until a reviewed policy exists.
- ⏳ **Gated** — *using* it in production stays blocked until ADR-002 Decision 7's non-engineering
  preconditions are met: a professional collaborator authors the `ProgressPolicy` — the signal
  itself: window K, thresholds, trends (**how to author it: `docs/PROGRESS_POLICY.md` + the inert
  template `docs/examples/progress_policy.template.json`**; context in
  `docs/M1_PROFESSIONAL_COLLABORATOR_BRIEF.md`) — a clinical-language review, and a DPIA
  progress-profiling touchpoint. The system will only ever *suggest*; a therapist decides
  (`kc suggestions` / `kc decide`), and every accepted premise still re-enters the full safety pipeline.

### Where it's heading — a multi-user program platform (ADR-005, gated)

Today's product is a **single-operator** tool. The next step (`docs/ADR_005_multi_user_program_platform.md`)
is a platform: a family / child / therapist account model, therapist-run programs, and
progress reporting to parents. Its **story-template** part (a) is already built (`kc author`,
above); accounts and **child date of birth** (parts b/c) **materially expand the personal data
we process and are deliberately gated** on a DPIA revision — assessed in
`docs/DPIA_ADDENDUM_accounts_and_dob.md` and `docs/RETENTION_ERASURE_DESIGN.md`, awaiting
DPO/counsel review. No accounts/DOB code ships before that clears.

## Family

Part of the WeGoFwd2020 portfolio (StudyBuddy OnDemand, Mentible, Pramana, Thittam). The name
is Tamil, alongside **Thittam**; the generation seam is the shared **`wegofwd-llm`** package.
