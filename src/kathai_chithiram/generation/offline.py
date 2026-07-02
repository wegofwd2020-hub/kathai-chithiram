"""Deterministic, local scene-script generation — no LLM, no network, no key.

The production path turns a story into a scene script through the ``wegofwd-llm``
seam (:func:`~kathai_chithiram.generation.generator.generate_scene_script`). This
module is a **deliberately non-LLM** alternative for manual verification and demos:
it segments the story into scenes by sentence, one caption per scene, with calm
defaults (fixed pacing, gentle fades, no flashing). It is *not* a story adaptation
— it does not rewrite, simplify, or safety-rephrase — so its output is only as
appropriate as the input text. The human review gate still applies before anything
reaches a child.

It shares the two guarantees that matter with the LLM path:

* **The child's name never enters the stored script (KC-2).** The story is
  pseudonymized to the mapping's token first; every caption is checked and a
  surviving identifier is a hard stop (:class:`IdentifierLeakError`).
* **The output is contract-valid.** The assembled script is validated against the
  scene-script contract + safety rules before it is returned, exactly like a
  generated one — an invalid script raises rather than rendering.
"""

from __future__ import annotations

import re
from typing import Any

from kathai_chithiram.generation.scene_builder import (
    DEFAULT_FPS,
    assemble_scene_script,
    build_scene_dict,
    guard_no_identifier,
)
from kathai_chithiram.privacy.pseudonymize import NameMapping, pseudonymize
from kathai_chithiram.scene_script.schema import MAX_CAPTION_CHARS

__all__ = ["DEFAULT_SCENE_DURATION_S", "MAX_OFFLINE_SCENES", "build_offline_scene_script"]

#: Seconds a scene runs when a fixed duration is requested (2–8 s band).
DEFAULT_SCENE_DURATION_S = 4
#: Cap on scenes so a very long story yields a bounded video (the rest is dropped,
#: which the caller is told about).
MAX_OFFLINE_SCENES = 40
#: A scene caption is grown to at least this many characters by grouping short
#: adjacent sentences, so a scene is never a tiny fragment (still capped at the
#: contract's caption limit).
MIN_CAPTION_CHARS = 40

_SENTENCE = re.compile(r"[^.!?]+[.!?]?")


def build_offline_scene_script(
    *,
    story_text: str,
    mapping: NameMapping,
    story_id: str,
    fps: int = DEFAULT_FPS,
    scene_duration_s: int | None = None,
    locale: str = "en-US",
    max_scenes: int = MAX_OFFLINE_SCENES,
) -> dict[str, Any]:
    """Assemble a contract-valid scene script from ``story_text``, locally.

    The story is pseudonymized, grouped into caption-sized scenes (short adjacent
    sentences are merged so a scene is never a tiny fragment; each caption ≤ the
    contract limit), and each scene gets a **setting inferred from its content** and
    a **duration sized to how long its caption takes to read**. The child's display
    name is never stored — the script carries the mapping's token.

    Args:
        story_text: The raw parent-authored story.
        mapping: The local identifier→token mapping for this child.
        story_id: Opaque id recorded on the script.
        fps: Frames per second (8–30).
        scene_duration_s: A fixed seconds-per-scene (2–8) to override the
            reading-time estimate; ``None`` (default) sizes each scene to its
            caption.
        locale: BCP-47-ish locale tag for the script.
        max_scenes: Cap on the number of scenes (excess captions are dropped).

    Returns:
        A validated scene-script document (safe to store and render).

    Raises:
        ValueError: If ``story_text`` has no usable text, or ``max_scenes`` < 1.
        IdentifierLeakError: If a child identifier survives pseudonymization in any
            caption (a hard stop — the name must never reach the stored script).
        SceneScriptInvalidError: If the assembled script fails contract/safety
            validation (a defensive check; should not happen for valid inputs).
    """
    if max_scenes < 1:
        raise ValueError("max_scenes must be at least 1")

    tokenized = pseudonymize(story_text, mapping)
    captions = _captions(tokenized, max_scenes)
    if not captions:
        raise ValueError("story has no usable text to turn into scenes")

    guard_no_identifier(captions, mapping)  # KC-2: the name must never reach the script
    scenes = [
        build_scene_dict(index, caption, duration_s=scene_duration_s)
        for index, caption in enumerate(captions, start=1)
    ]
    return assemble_scene_script(
        scenes=scenes,
        story_id=story_id,
        title=f"{mapping.token}'s story",
        fps=fps,
        locale=locale,
    )


def _captions(tokenized_text: str, max_scenes: int) -> list[str]:
    """Group pseudonymized text into ≤ ``max_scenes`` caption strings.

    Sentences are the unit; a sentence longer than the caption limit is first broken
    into word-bounded chunks that fit. Short adjacent units are then merged so a
    caption reaches at least ``MIN_CAPTION_CHARS`` (never exceeding the contract
    limit), so a scene is a readable line rather than a two-word fragment.
    """
    units: list[str] = []
    for sentence in _SENTENCE.findall(tokenized_text):
        cleaned = " ".join(sentence.split())  # collapse whitespace/newlines
        if cleaned:
            units.extend(_chunk(cleaned, MAX_CAPTION_CHARS))

    captions: list[str] = []
    current = ""
    for unit in units:
        if not current:
            current = unit
        elif len(current) < MIN_CAPTION_CHARS and len(current) + 1 + len(unit) <= MAX_CAPTION_CHARS:
            current = f"{current} {unit}"  # merge a short caption with the next unit
        else:
            captions.append(current)
            current = unit
        if len(captions) >= max_scenes:
            return captions[:max_scenes]
    if current and len(captions) < max_scenes:
        captions.append(current)
    return captions[:max_scenes]


def _chunk(text: str, limit: int) -> list[str]:
    """Break ``text`` into pieces of at most ``limit`` characters on word bounds."""
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current = ""
    for word in text.split():
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
        # A single word longer than the limit is hard-sliced.
        while len(word) > limit:
            chunks.append(word[:limit])
            word = word[limit:]
        current = word
    if current:
        chunks.append(current)
    return chunks
