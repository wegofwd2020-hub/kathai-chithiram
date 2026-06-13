"""Generation-side concerns that shape what the LLM produces.

Currently the content-safety system prompt (``docs/CONTENT_SAFETY.md`` §5.1):
the MUST / MUST-NOT rules encoded as model instructions, the first enforcement
point in the pipeline. Generation runs through the ``wegofwd-llm`` seam, which
forwards this prompt to whichever provider is configured.
"""

from __future__ import annotations

from kathai_chithiram.generation.system_prompt import (
    MUST,
    MUST_NOT,
    build_generation_system_prompt,
)

__all__ = ["MUST", "MUST_NOT", "build_generation_system_prompt"]
