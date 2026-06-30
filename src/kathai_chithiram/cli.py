"""Command-line entry point: a parent's story to a draft animation.

One command wires the whole pipeline behind the contract::

    read story -> generate (wegofwd-llm seam) -> validate (KC-3)
               -> store (story.txt + scene_script.json)
               -> render a DRAFT animation (KC-4 guards run)

Two safety boundaries are enforced here, not assumed:

* **Privacy.** The ``--child-name`` is used only to build the pseudonymization
  mapping. The raw story (which may name the child) is stored as ``story.txt``;
  the scene script stores only the ``CHILD`` token; the real name is reinserted
  into captions *at render time only*, never into the stored script or the
  console. Sending story text also requires the operator to assert the
  provider's no-training / zero-retention posture (``--provider-no-train-zdr``),
  or generation refuses before anything leaves the device.
* **Human review.** A rendered animation is a *draft*. It is never marked
  delivered; the operator must review it (and the captioned scene script) before
  it reaches a child (CLAUDE.md human-in-the-loop gate).

Run ``python -m kathai_chithiram.cli --help`` (or the installed ``kc`` command).
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kathai_chithiram.errors import KathaiChithiramError
from kathai_chithiram.generation import generate_scene_script
from kathai_chithiram.privacy import NameMapping
from kathai_chithiram.rendering import SceneScriptRenderer
from kathai_chithiram.storage import StoryArtifactStore
from kathai_chithiram.wegofwd_llm.anthropic_provider import DEFAULT_MODEL
from kathai_chithiram.wegofwd_llm.provider import LLMProvider, ProviderConfig

__all__ = ["build_arg_parser", "main"]


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the ``kc`` command."""
    parser = argparse.ArgumentParser(
        prog="kc",
        description="Turn a parent's story into a draft captioned animation.",
    )
    parser.add_argument(
        "story",
        help="Path to the parent's story (UTF-8 text). Use '-' to read from stdin.",
    )
    parser.add_argument(
        "--child-name",
        required=True,
        help="The child's name. Used only to strip/reinsert; never stored or logged.",
    )
    parser.add_argument(
        "--story-id",
        default=None,
        help="Opaque story id (safe chars only). Defaults to a random UUID.",
    )
    parser.add_argument(
        "--store-root",
        type=Path,
        default=Path("kc_store"),
        help="Directory the story's artifacts are written under (default: ./kc_store).",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Anthropic model id (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--effort",
        default="high",
        choices=["low", "medium", "high", "xhigh", "max"],
        help="Reasoning effort for generation (default: high).",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help="Maximum generation attempts including repairs (default: 3).",
    )
    parser.add_argument(
        "--provider-no-train-zdr",
        action="store_true",
        help=(
            "Assert the provider org is configured for no-training AND "
            "zero-retention. Required to send story text; generation refuses "
            "without it."
        ),
    )
    parser.add_argument(
        "--no-render",
        action="store_true",
        help="Stop after producing and storing the scene script (skip rendering).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Also write a copy of the rendered draft animation to this path.",
    )
    return parser


def _read_story(source: str) -> str:
    """Read story text from a file path, or from stdin when ``source`` is '-'.

    Args:
        source: A filesystem path, or ``"-"`` for stdin.

    Returns:
        The story text.

    Raises:
        FileNotFoundError: If the path does not exist.
        ValueError: If the story is empty.
    """
    text = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("story is empty")
    return text


def _load_default_renderer() -> SceneScriptRenderer:
    """Import and construct the matplotlib reference renderer.

    The reference renderers live at the repo root (not in the package), so this
    puts the repo root on ``sys.path`` before importing. Requires the optional
    ``[render]`` dependencies.

    Returns:
        A ready :class:`SceneScriptRenderer`.

    Raises:
        RuntimeError: If the renderer or its dependencies cannot be imported.
    """
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    try:
        from generate_animation import MatplotlibStickFigureRenderer
    except ImportError as exc:
        raise RuntimeError(
            "could not load the matplotlib renderer; install the render extra "
            "(pip install 'kathai-chithiram[render]') and run from the repo root, "
            "or pass --no-render"
        ) from exc
    renderer: SceneScriptRenderer = MatplotlibStickFigureRenderer()
    return renderer


def _render_draft(
    *,
    renderer: SceneScriptRenderer,
    store: StoryArtifactStore,
    story_id: str,
    script: dict[str, Any],
    mapping: NameMapping,
    extra_out: Path | None,
) -> Path:
    """Render a guarded draft animation and file it under the story's media dir.

    The render-time safety guards (KC-4) run inside ``renderer.render``; an
    unsafe output raises and leaves nothing behind.

    Returns:
        The path of the stored media file.
    """
    with tempfile.TemporaryDirectory() as tmp:
        draft = Path(tmp) / "animation.mp4"
        renderer.render(script, mapping=mapping, output_path=str(draft))
        data = draft.read_bytes()
    media_path = store.add_media(story_id, "animation.mp4", data)
    if extra_out is not None:
        extra_out.parent.mkdir(parents=True, exist_ok=True)
        extra_out.write_bytes(data)
    return media_path


def main(argv: Sequence[str] | None = None, *, provider: LLMProvider | None = None) -> int:
    """Run the CLI; return a process exit code.

    Args:
        argv: Argument vector (defaults to ``sys.argv[1:]``).
        provider: Optional pre-built provider (for tests/embedding). When
            ``None`` a real :class:`AnthropicProvider` is constructed, which
            needs ``ANTHROPIC_API_KEY`` in the environment.

    Returns:
        ``0`` on success; ``2`` on a handled, user-facing error.
    """
    args = build_arg_parser().parse_args(argv)
    story_id = args.story_id or uuid.uuid4().hex

    try:
        story_text = _read_story(args.story)
    except (OSError, ValueError) as exc:
        print(f"error: cannot read story: {exc}", file=sys.stderr)
        return 2

    mapping = NameMapping.for_child(args.child_name)

    if provider is None:
        provider = _build_anthropic_provider(model=args.model, effort=args.effort)
        if provider is None:
            return 2

    config = ProviderConfig(
        provider_id=f"anthropic:{args.model}",
        no_training=args.provider_no_train_zdr,
        zero_retention=args.provider_no_train_zdr,
    )

    try:
        result = generate_scene_script(
            story_text=story_text,
            mapping=mapping,
            provider=provider,
            config=config,
            request_id=story_id,
            max_attempts=args.max_attempts,
        )
    except KathaiChithiramError as exc:
        print(f"error: generation failed: {exc}", file=sys.stderr)
        if not args.provider_no_train_zdr:
            print(
                "hint: pass --provider-no-train-zdr to assert the provider's "
                "no-training / zero-retention posture before sending story text.",
                file=sys.stderr,
            )
        return 2

    store = StoryArtifactStore(args.store_root)
    store.create_story(
        story_id,
        created_at=datetime.now(timezone.utc),
        story_text=story_text,
    )
    store.write_scene_script(story_id, result.script)

    _print_summary(story_id=story_id, store=store, result=result)

    if args.no_render:
        print("\nScene script stored. Skipped rendering (--no-render).")
        return 0

    try:
        renderer = _load_default_renderer()
        media_path = _render_draft(
            renderer=renderer,
            store=store,
            story_id=story_id,
            script=result.script,
            mapping=mapping,
            extra_out=args.out,
        )
    except (RuntimeError, KathaiChithiramError) as exc:
        print(f"error: render failed: {exc}", file=sys.stderr)
        print("(the scene script was generated and stored; only rendering failed)", file=sys.stderr)
        return 2

    print(f"\nDraft animation: {media_path}")
    if args.out is not None:
        print(f"Copy written to: {args.out}")
    print(
        "\n⚠  DRAFT — a human must review this animation (and the captioned "
        "scene script) before it is shown to a child. It is NOT marked delivered."
    )
    return 0


def _build_anthropic_provider(*, model: str, effort: str) -> LLMProvider | None:
    """Construct the real provider, printing a friendly error on failure.

    Returns ``None`` (and prints guidance) if the SDK is missing or no API key
    is configured, so the caller can exit cleanly.
    """
    import os

    from kathai_chithiram.errors import ProviderUnavailableError
    from kathai_chithiram.wegofwd_llm.anthropic_provider import AnthropicProvider

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "error: ANTHROPIC_API_KEY is not set; export it before running "
            "(or pass a provider when embedding).",
            file=sys.stderr,
        )
        return None
    try:
        return AnthropicProvider(model=model, effort=effort)
    except ProviderUnavailableError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return None


def _print_summary(
    *, story_id: str, store: StoryArtifactStore, result: Any
) -> None:
    """Print a console summary using the token form (no real name)."""
    script = result.script
    print(f"story_id: {story_id}")
    print(f"stored under: {store.story_dir(story_id)}")
    print(f"generation attempts: {result.attempts}")
    print(
        f"title: {script['title']}  |  scenes: {len(script['scenes'])}  |  "
        f"{script['total_duration_s']}s @ {script['fps']}fps  |  {script['locale']}"
    )
    print("scenes (child shown as token; name appears only in the rendered video):")
    for scene in script["scenes"]:
        print(f"  {scene['index']}. [{scene['duration_s']}s] {scene['narration']}")


if __name__ == "__main__":
    raise SystemExit(main())
