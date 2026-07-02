# Story template — write a story without writing prose

Instead of writing a paragraph, you fill a small **template**: a **title** and an
ordered list of **steps**, one per moment of the routine from beginning to end. Each
step becomes one calm scene in the animation. It runs with **no AI and no API key**.

This is ADR-005 part (a). It collects the same data as the rest of the app — your
story and the child's first name — and **nothing more**: the name is only used to say
it in the video and is never stored in the script. Every draft is still reviewed by a
human before a child sees it.

## The shape

A template is a JSON file:

```json
{
  "title": "Silas Brushes His Teeth",
  "steps": [
    { "text": "Silas stands at the sink and takes a slow breath." },
    { "text": "He picks up his toothbrush.", "props": ["toothbrush"] },
    { "text": "He brushes gently in small circles." },
    { "text": "He rinses and smiles proudly at the mirror.", "expression": "happy" }
  ]
}
```

- **`title`** — the story's title. May include the child's name (it's stripped).
- **`steps`** — the routine, in order. **One step → one scene.** Keep each `text`
  short (a single clear sentence); it becomes the on-screen caption and narration.

That's all you need. Everything below is optional.

## Optional per-step details

Leave any of these out and it's inferred from the step's text; set it to take
control:

| Field | What it does | Example |
|---|---|---|
| `setting` | The backdrop | `"a bathroom"`, `"a bedroom"`, `"a kitchen"`, `"outdoors"` |
| `props` | Small objects drawn in the scene | `["toothbrush", "cup"]` |
| `expression` | The child's face | `"happy"`, `"calm"`, `"sleepy"`, `"worried"` |
| `pose` | The child's pose | `"standing"`, `"waving"` |
| `sfx` | Sound-effect cue names (need a `--sfx` sound bank to be heard) | `["water_running"]` |

Optional at the top level: `"fps"` (8–30, default 24) and `"locale"` (default
`"en-US"`).

## Make the video

```bash
kc author story.json --child-name Silas --out video.mp4 --captions srt
```

### Or author interactively (no file)

Omit the file and `kc author` walks you through it — a title, then one step per
line, Enter on a blank line to finish. Each step's setting/props/mood are inferred
from what you type (the JSON file is how you set those by hand).

```bash
kc author --child-name Silas --out video.mp4
```
```
Story title: Silas Brushes His Teeth
  Step 1: Silas stands at the sink and takes a slow breath.
  Step 2: He picks up his toothbrush.
  Step 3: He rinses and smiles proudly.
  Step 4:            ← blank line finishes
```

Add narration or sound the same way as the other flows:
`--voice 'espeak-ng -w {out} {text}'`, `--sfx ./sounds`, `--character-voice ...`.

The result is a **draft**: review it (`kc review <id> --show`) before it reaches a
child.

## Preview before you render

Add `--dry-run` to see exactly what your template becomes — the scenes, their inferred
settings/props/mood, and durations — **without storing or rendering anything**:

```bash
kc author story.json --child-name Silas --dry-run
```

## Ready-made examples

Three starter templates live in [`docs/examples/`](examples/) — copy one and edit:

- [`brushing_teeth.json`](examples/brushing_teeth.json) — a bathroom routine
- [`bedtime_routine.json`](examples/bedtime_routine.json) — a calm bedtime
- [`going_to_the_park.json`](examples/going_to_the_park.json) — an outing

They use the name **Alex**; run with `--child-name Alex` (or change the name in both the
text and the flag to your child's):

```bash
kc author docs/examples/brushing_teeth.json --child-name Alex --dry-run
```

## Good template habits

- One idea per step — short steps read more calmly than long ones.
- Order the steps exactly as the routine happens, start to finish.
- Say the child's name naturally in the text; it's replaced at render time.
- Prefer letting `setting`/`props`/`expression` infer; only set them when the text
  doesn't make the moment obvious.
