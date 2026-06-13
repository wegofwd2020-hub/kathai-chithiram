"""Kathai Chithiram — parent's story to a calm, captioned animation for a child.

Pipeline seams: ``parent story -> generation (wegofwd-llm) -> scene script ->
renderer -> animation``. The scene script is the stable contract between
generation and rendering (see ``docs/SCENE_SCRIPT_CONTRACT.md``).
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
