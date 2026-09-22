"""Subprocess adapter: run BlenderGreasePencilRenderer inside a Blender process.

``bpy`` is only available inside Blender — this module lets the ``kc`` CLI use
the Blender renderer without importing ``bpy`` directly. It validates the scene
script in-process, serialises it to a temp file, spawns Blender, and waits for
the result.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any, ClassVar

from kathai_chithiram.errors import RendererError
from kathai_chithiram.privacy.pseudonymize import NameMapping
from kathai_chithiram.rendering.narration import NarrationSynthesizer, VoiceCast
from kathai_chithiram.rendering.pipeline import (
    RenderPlan,
    RenderResult,
    SceneScriptRenderer,
    build_render_plan,
)
from kathai_chithiram.rendering.safety import RenderSafetyReport
from kathai_chithiram.rendering.sfx import SfxSynthesizer
from kathai_chithiram.scene_script.validation import validate_scene_script
from kathai_chithiram.scene_script.vocabulary import Prop

__all__ = ["BlenderSubprocessRenderer"]

# Structural safety report: the GP renderer is calm by construction (fixed
# palette, no audio, gentle fades), so a constant report is correct here.
_CALM_REPORT = RenderSafetyReport(
    fps=8,
    luminances=[0.7],
    narration_volume=0.0,
    sfx_levels=[],
)


def _find_blender() -> str:
    """Return the path to the Blender binary.

    Checks ``KC_BLENDER_BIN`` first, then ``PATH``.

    Returns:
        Absolute path to the Blender binary.

    Raises:
        RendererError: If Blender cannot be located.
    """
    from_env = os.environ.get("KC_BLENDER_BIN")
    if from_env:
        return from_env
    found = shutil.which("blender")
    if found:
        return found
    raise RendererError(
        "blender binary not found; set KC_BLENDER_BIN or add blender to PATH"
    )


def _find_script() -> str:
    """Return the absolute path to ``blender_animation.py`` at the repo root.

    Returns:
        Absolute path string.

    Raises:
        RendererError: If the script is not found.
    """
    # blender_animation.py lives at repo root:
    # src/kathai_chithiram/rendering/ → parents[3] = repo root
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "blender_animation.py"
    if not script.exists():
        raise RendererError(
            f"blender_animation.py not found at expected path: {script}"
        )
    return str(script)


class BlenderSubprocessRenderer(SceneScriptRenderer):
    """Run the Blender Grease-Pencil renderer in a Blender subprocess.

    Validates the scene script in-process (fast fail), then spawns
    ``blender --background --python blender_animation.py -- --input ... --output ...``.
    Blender handles the full validate→draw→guard→promote lifecycle internally.
    Blender's stderr is streamed live so the user sees progress.

    Audio (narration, sfx) is not yet supported on this path — pass those to
    the matplotlib renderer, or omit them. Passing ``narration`` or ``sfx``
    raises :class:`RendererError`.
    """

    name: ClassVar[str] = "blender-grease-pencil-v2"
    supported_majors: ClassVar[frozenset[int]] = frozenset({1, 2})

    def drawable_props(self) -> frozenset[Prop]:
        """Return the props the wrapped GP renderer can draw.

        Imports ``BLENDER_DRAWABLE_PROPS`` from ``blender_animation`` without
        loading ``bpy`` — the constant is set at module level before any lazy
        ``bpy`` import.

        Returns:
            The drawable prop set.
        """
        repo_root = str(Path(__file__).resolve().parents[3])
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        from blender_animation import BLENDER_DRAWABLE_PROPS  # noqa: PLC0415
        return BLENDER_DRAWABLE_PROPS

    def render(  # type: ignore[override]
        self,
        script: Mapping[str, Any],
        *,
        mapping: NameMapping | None = None,
        output_path: str | None = None,
        narration: NarrationSynthesizer | VoiceCast | None = None,
        sfx: SfxSynthesizer | None = None,
    ) -> RenderResult:
        """Validate, spawn Blender, wait, promote output.

        Overrides the base ``render()`` entirely — the subprocess owns the full
        validate→draw→guard→promote lifecycle.

        Args:
            script: The scene-script document.
            mapping: Optional name mapping for render-time name reinsertion.
            output_path: Where to write the final MP4. When ``None``, Blender
                builds the scene without writing a file.
            narration: Not yet supported on the Blender path; pass ``None``.
            sfx: Not yet supported on the Blender path; pass ``None``.

        Returns:
            A :class:`RenderResult` on success.

        Raises:
            SceneScriptInvalidError: If the script fails validation before the
                subprocess is even started.
            RendererError: If Blender is not found, the adapter script is
                missing, Blender exits nonzero, or the output file is absent
                after a successful exit.
            RendererError: If ``narration`` or ``sfx`` are supplied (not yet
                supported on this path).
        """
        if narration is not None:
            raise RendererError(
                "narration audio is not yet supported on the Blender renderer path"
            )
        if sfx is not None:
            raise RendererError(
                "sound effects are not yet supported on the Blender renderer path"
            )

        validate_scene_script(script)
        blender_bin = _find_blender()
        script_path = _find_script()

        with tempfile.TemporaryDirectory() as tmp:
            script_json = os.path.join(tmp, "script.json")
            with open(script_json, "w", encoding="utf-8") as fh:
                json.dump(dict(script), fh)

            cmd = [
                blender_bin,
                "--background",
                "--python", script_path,
                "--",
                "--input", script_json,
            ]

            tmp_out: str | None = None
            if output_path is not None:
                tmp_out = os.path.join(tmp, "output.mp4")
                cmd += ["--output", tmp_out]

            if mapping is not None:
                mapping_json = os.path.join(tmp, "mapping.json")
                with open(mapping_json, "w", encoding="utf-8") as fh:
                    json.dump(
                        {
                            "identifiers": list(mapping.identifiers),
                            "token": mapping.token,
                            "display_name": mapping.display_name,
                        },
                        fh,
                    )
                cmd += ["--name-mapping", mapping_json]

            proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True)
            stderr_lines: list[str] = []
            try:
                if proc.stderr is None:
                    raise RendererError("subprocess.Popen did not open stderr pipe")
                for line in proc.stderr:
                    sys.stderr.write(line)
                    stderr_lines.append(line)
                proc.wait()
            except KeyboardInterrupt:
                proc.terminate()
                proc.wait()
                raise

            if proc.returncode != 0:
                tail = "".join(stderr_lines[-20:])
                raise RendererError(
                    f"Blender exited {proc.returncode}:\n{tail}"
                )

            if output_path is not None:
                if tmp_out is None:
                    raise RendererError("internal: output temp path was not initialized")
                if not os.path.exists(tmp_out):
                    raise RendererError(
                        "Blender exited 0 but output not found at expected path"
                    )
                try:
                    os.replace(tmp_out, output_path)
                except OSError as exc:
                    raise RendererError(
                        f"failed to move rendered output to {output_path}: {exc}"
                    ) from exc

        plan = build_render_plan(script, mapping=mapping)
        return RenderResult(
            plan=plan,
            safety_report=_CALM_REPORT,
            output_path=output_path,
            has_audio=False,
        )

    def _render(self, plan: RenderPlan, *, draft_path: str | None) -> RenderSafetyReport:
        """Never called — ``render()`` is fully overridden.

        Args:
            plan: The validated, name-reinserted render plan.
            draft_path: Where to write the draft artifact, or ``None``.

        Raises:
            NotImplementedError: Always — this method is unreachable; the
                full lifecycle is handled by :meth:`render`.
        """
        raise NotImplementedError(
            "BlenderSubprocessRenderer.render() bypasses _render(); "
            "this method should never be called"
        )
