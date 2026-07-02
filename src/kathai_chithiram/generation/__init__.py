"""Generation-side concerns that shape what the LLM produces.

Two layers live here, both feeding the ``wegofwd-llm`` seam:

* the content-safety system prompt (``docs/CONTENT_SAFETY.md`` §5.1) — the
  MUST / MUST-NOT rules encoded as model instructions, plus the scene-script
  contract and a worked example (:mod:`~.scene_script_prompt`);
* the generation orchestrator (:func:`generate_scene_script`) — the
  prompt → seam → parse → validate → repair loop that yields a contract-valid
  scene script (never an unvalidated one).
"""

from __future__ import annotations

from kathai_chithiram.generation.generator import (
    GeneratedSceneScript,
    generate_scene_script,
)
from kathai_chithiram.generation.offline import build_offline_scene_script
from kathai_chithiram.generation.scene_script_prompt import (
    EXAMPLE_SCENE_SCRIPT,
    build_scene_script_system_prompt,
)
from kathai_chithiram.generation.system_prompt import (
    MUST,
    MUST_NOT,
    build_generation_system_prompt,
)

__all__ = [
    "EXAMPLE_SCENE_SCRIPT",
    "MUST",
    "MUST_NOT",
    "GeneratedSceneScript",
    "build_generation_system_prompt",
    "build_offline_scene_script",
    "build_scene_script_system_prompt",
    "generate_scene_script",
]
