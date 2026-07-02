"""Guided, structured story authoring (ADR-005 Decision 6).

A parent fills a :class:`~kathai_chithiram.authoring.template.StoryTemplate` — a
title and ordered steps — instead of writing free prose, and it lowers
deterministically (no LLM, no key) to the scene-script contract the renderer
consumes. Adds no new personal data; the child's name is stripped at lowering
(KC-2), so this is not behind ADR-005's identity/DOB privacy gate.
"""

from __future__ import annotations

from kathai_chithiram.authoring.template import (
    MAX_TEMPLATE_STEPS,
    StoryStep,
    StoryTemplate,
    load_template,
    template_from_mapping,
    template_to_scene_script,
)

__all__ = [
    "MAX_TEMPLATE_STEPS",
    "StoryStep",
    "StoryTemplate",
    "load_template",
    "template_from_mapping",
    "template_to_scene_script",
]
