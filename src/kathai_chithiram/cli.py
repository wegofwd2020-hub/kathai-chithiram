"""Command-line entry point: a parent's story to a draft animation.

Two subcommands sit on the same pipeline behind the contract:

* ``kc intake`` — the parent-facing flow. Walks a parent through explicit
  consent, then their child's first name and story, and runs intake
  (consent gate -> generate -> store -> render a review-gated draft).
* ``kc generate`` — the operator/non-interactive flow. Takes the story as a
  file/stdin plus flags; useful for scripting and tests.
* ``kc review`` — the reviewer flow (KC-7). Shows a stored draft and records an
  approve (which marks it delivered) or reject decision.

The first two enforce the same boundaries: the child's name builds the
pseudonymization mapping only (never stored or logged; reinserted into captions
at render time), and every rendered animation is a *draft* that a human must
review before it reaches a child (CLAUDE.md) — ``kc review`` is where that human
decision is recorded. Run ``python -m kathai_chithiram.cli --help`` or the
installed ``kc`` command.
"""

from __future__ import annotations

import argparse
import os
import shlex
import sys
import uuid
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wegofwd_video.errors import VideoError

from kathai_chithiram.access import GuardedStore, JsonlAuditSink, Principal, Role
from kathai_chithiram.errors import KathaiChithiramError
from kathai_chithiram.generation import generate_scene_script
from kathai_chithiram.intake import (
    Consent,
    ParentSubmission,
    format_notice_preamble,
    submit_intake,
)
from kathai_chithiram.privacy import NameMapping
from kathai_chithiram.rendering import CliTtsSynthesizer, NarrationSynthesizer, SceneScriptRenderer
from kathai_chithiram.review import ReviewDecision, load_review_bundle, review_story
from kathai_chithiram.storage import StoryArtifactStore, StoryStore
from kathai_chithiram.video import generate_story_video
from kathai_chithiram.wegofwd_llm.anthropic_provider import DEFAULT_MODEL
from kathai_chithiram.wegofwd_llm.provider import LLMProvider, ProviderConfig

__all__ = ["build_arg_parser", "main"]

#: Filename for the review-gated draft animation under a story's ``media/`` dir.
_DRAFT_MEDIA_FILENAME = "animation.mp4"


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the ``kc`` command."""
    parser = argparse.ArgumentParser(
        prog="kc",
        description="Turn a parent's story into a draft captioned animation.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    intake = sub.add_parser(
        "intake", help="Interactive parent flow: consent, name, story -> draft."
    )
    _add_common_args(intake)

    generate = sub.add_parser(
        "generate", help="Non-interactive: generate from a story file/stdin."
    )
    generate.add_argument(
        "story",
        help="Path to the parent's story (UTF-8 text). Use '-' to read from stdin.",
    )
    generate.add_argument(
        "--child-name",
        required=True,
        help="The child's name. Used only to strip/reinsert; never stored or logged.",
    )
    generate.add_argument(
        "--provider-no-train-zdr",
        action="store_true",
        help=(
            "Assert the provider org is configured for no-training AND "
            "zero-retention. Required to send story text; generation refuses "
            "without it. Backed by a dedicated key in ANTHROPIC_ZDR_API_KEY."
        ),
    )
    _add_common_args(generate)

    review = sub.add_parser(
        "review", help="Review a stored draft: show, approve, or reject."
    )
    review.add_argument("story_id", help="Opaque id of the story to review.")
    review.add_argument(
        "--store-root",
        type=Path,
        default=Path("kc_store"),
        help="Directory the story's artifacts live under (default: ./kc_store).",
    )
    action = review.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--show",
        action="store_true",
        help="Show the draft, scene-script summary, and consent record.",
    )
    action.add_argument(
        "--approve",
        action="store_true",
        help="Approve the draft and mark the story delivered.",
    )
    action.add_argument(
        "--reject",
        action="store_true",
        help="Reject the draft; it stays undelivered (retention will reclaim it).",
    )
    review.add_argument(
        "--reviewer",
        default=None,
        help="Reviewer identity recorded in the decision (required to approve/reject).",
    )
    review.add_argument(
        "--reason",
        default=None,
        help="Reason for the decision (required when rejecting).",
    )

    assign = sub.add_parser(
        "assign", help="Grant a reviewer/therapist role on a story (owner only)."
    )
    assign.add_argument("story_id", help="Opaque id of the story to grant a role on.")
    assign.add_argument(
        "--principal",
        required=True,
        help="Opaque id of the principal to grant the role to.",
    )
    assign.add_argument(
        "--role",
        required=True,
        choices=[Role.REVIEWER.value, Role.THERAPIST.value],
        help="Role to grant (reviewer or therapist).",
    )
    assign.add_argument(
        "--store-root",
        type=Path,
        default=Path("kc_store"),
        help="Directory the story's artifacts live under (default: ./kc_store).",
    )
    return parser


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    """Add the flags shared by every subcommand."""
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
    parser.add_argument(
        "--voice",
        default=None,
        metavar="CMD_TEMPLATE",
        help=(
            "Add narration audio using a local command-line TTS engine. Pass the "
            "command with '{out}' and '{text}' tokens, e.g. "
            "--voice 'espeak-ng -w {out} {text}'. Runs locally — the child's name "
            "stays on this machine — and needs the render extra plus the engine "
            "installed. Omit for a silent (video-only) draft."
        ),
    )


def main(argv: Sequence[str] | None = None, *, provider: LLMProvider | None = None) -> int:
    """Run the CLI; return a process exit code (``0`` ok, ``2`` handled error)."""
    args = build_arg_parser().parse_args(argv)
    if args.command == "intake":
        return _cmd_intake(args, provider=provider)
    if args.command == "review":
        return _cmd_review(args)
    if args.command == "assign":
        return _cmd_assign(args)
    return _cmd_generate(args, provider=provider)


def _cmd_generate(args: argparse.Namespace, *, provider: LLMProvider | None) -> int:
    """The non-interactive generate flow."""
    story_id = args.story_id or uuid.uuid4().hex
    try:
        story_text = _read_story(args.story)
    except (OSError, ValueError) as exc:
        print(f"error: cannot read story: {exc}", file=sys.stderr)
        return 2

    store = _open_guarded_store(args.store_root, warn_if_plaintext=True)
    if store is None:
        return 2

    mapping = NameMapping.for_child(args.child_name)

    if provider is None:
        provider = _build_anthropic_provider(model=args.model, effort=args.effort)
        if provider is None:
            return 2

    # The posture is backed by the dedicated ZDR key the provider was built with
    # (KC-6); the key class is recorded in the audit id.
    config = ProviderConfig(
        provider_id=f"anthropic:{args.model}:zdr-key",
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

    store.create_story(story_id, created_at=datetime.now(timezone.utc), story_text=story_text)
    store.write_scene_script(story_id, result.script)
    _print_summary(story_id=story_id, store=store, generated=result)

    return _maybe_render(
        args, store=store, story_id=story_id, script=result.script, mapping=mapping
    )


def _cmd_review(args: argparse.Namespace) -> int:
    """The reviewer flow: show a draft, or record an approve/reject decision."""
    store = _open_guarded_store(args.store_root)
    if store is None:
        return 2
    try:
        bundle = load_review_bundle(store, args.story_id)
    except KathaiChithiramError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"error: cannot load story for review: {exc}", file=sys.stderr)
        return 2

    if args.show:
        _print_review_bundle(bundle)
        return 0

    if not args.reviewer:
        print("error: --reviewer is required to approve or reject.", file=sys.stderr)
        return 2

    decision = ReviewDecision.APPROVED if args.approve else ReviewDecision.REJECTED
    try:
        record = review_story(
            store,
            args.story_id,
            decision=decision,
            reviewer=args.reviewer,
            reason=args.reason,
        )
    except KathaiChithiramError as exc:
        print(f"error: review failed: {exc}", file=sys.stderr)
        return 2

    if record.approved:
        print(
            f"\n✓ Approved by {record.reviewer}. Story {args.story_id} is marked "
            "delivered and will no longer be purged by the retention sweep."
        )
    else:
        print(
            f"\n✗ Rejected by {record.reviewer}. Story {args.story_id} stays "
            "undelivered and will be reclaimed by the retention sweep."
        )
    return 0


def _cmd_assign(args: argparse.Namespace) -> int:
    """Grant a reviewer/therapist role on a story (owner-only; ADR-004 / KC-11)."""
    store = _open_guarded_store(args.store_root)
    if store is None:
        return 2
    role = Role(args.role)  # argparse restricts to assignable role values
    try:
        store.assign_role(args.story_id, args.principal, role)
    except KathaiChithiramError as exc:
        print(f"error: assign failed: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"✓ Granted {role.value} on {args.story_id} to {args.principal}.")
    return 0


def _print_review_bundle(bundle: Any) -> None:
    """Print the materials a reviewer needs to judge a draft."""
    print(f"story_id: {bundle.story_id}")
    print(f"delivered: {bundle.metadata.delivered}")
    if bundle.existing_review is not None:
        prior = bundle.existing_review
        print(
            f"prior decision: {prior.get('decision')} by {prior.get('reviewer')} "
            f"at {prior.get('decided_at')}"
        )

    script = bundle.scene_script
    print(
        f"\ntitle: {script['title']}  |  scenes: {len(script['scenes'])}  |  "
        f"{script['total_duration_s']}s @ {script['fps']}fps  |  {script['locale']}"
    )
    print("scenes (child shown as token; the real name appears only in the video):")
    for scene in script["scenes"]:
        print(f"  {scene['index']}. [{scene['duration_s']}s] {scene['narration']}")

    if bundle.media_paths:
        print("\nrendered draft(s) to watch before deciding:")
        for path in bundle.media_paths:
            print(f"  {path}")
    else:
        print("\n⚠  No rendered draft yet — approval is blocked until one is rendered.")

    if bundle.intake_record is not None:
        consent = bundle.intake_record.get("consent", {})
        posture = bundle.intake_record.get("provider_posture", {})
        print("\nconsent on file:")
        for key, value in consent.items():
            print(f"  {key}: {value}")
        print(
            f"provider posture: {posture.get('provider_id')} "
            f"(no_training={posture.get('no_training')}, "
            f"zero_retention={posture.get('zero_retention')})"
        )
        warnings = bundle.intake_record.get("minimization_warnings") or []
        if warnings:
            print("minimization warnings raised at intake:")
            for warning in warnings:
                print(f"  • {warning}")
    else:
        print("\nconsent on file: (none — story was created via `generate`)")

    print(
        "\nTo record a decision:\n"
        f"  kc review {bundle.story_id} --approve --reviewer NAME\n"
        f"  kc review {bundle.story_id} --reject  --reviewer NAME --reason \"...\""
    )


def _cmd_intake(
    args: argparse.Namespace,
    *,
    provider: LLMProvider | None,
    input_fn: Callable[[str], str] = input,
    story_reader: Callable[[], str] | None = None,
) -> int:
    """The interactive parent-facing intake flow.

    ``input_fn`` and ``story_reader`` are injectable so the prompts can be driven
    deterministically in tests.
    """
    read_story = story_reader if story_reader is not None else sys.stdin.read

    submission = _collect_submission(input_fn=input_fn, story_reader=read_story)
    if submission is None:
        return 2

    if provider is None:
        provider = _build_anthropic_provider(model=args.model, effort=args.effort)
        if provider is None:
            return 2

    store = _open_guarded_store(args.store_root, warn_if_plaintext=True)
    if store is None:
        return 2
    try:
        result = submit_intake(
            submission,
            provider=provider,
            store=store,
            story_id=args.story_id,
            model_id=args.model,
            max_attempts=args.max_attempts,
        )
    except KathaiChithiramError as exc:
        print(f"error: intake failed: {exc}", file=sys.stderr)
        return 2

    print("\n✓ Consent recorded.")
    _print_summary(story_id=result.story_id, store=store, generated=result.generated)
    if result.warnings:
        print("\nA note on what you shared (your story was still accepted):")
        for warning in result.warnings:
            print(f"  • {warning}")

    mapping = NameMapping.for_child(
        submission.child_first_name, nickname=submission.child_nickname
    )
    return _maybe_render(
        args, store=store, story_id=result.story_id, script=result.generated.script, mapping=mapping
    )


def _collect_submission(
    *, input_fn: Callable[[str], str], story_reader: Callable[[], str]
) -> ParentSubmission | None:
    """Run the interactive intake prompts; return a submission or ``None``.

    Returns ``None`` (and prints why) if consent is declined or the story is
    empty — in either case nothing should be processed.
    """
    print("Kathai Chithiram — story intake\n")
    print(format_notice_preamble())
    print("\nBefore we begin, please confirm:")
    consent = Consent(
        is_guardian=_ask_yes_no(
            input_fn, "  [1] I am the parent/legal guardian of this child."
        ),
        ai_processing=_ask_yes_no(
            input_fn,
            "  [2] I consent to my story being sent to an AI provider configured "
            "for no-training / zero-retention.",
        ),
        human_review_ack=_ask_yes_no(
            input_fn,
            "  [3] I understand the animation is reviewed by a human before it is "
            "shown to my child.",
        ),
    )
    if not consent.granted:
        print(
            "\nWe can only proceed once all three are confirmed. Nothing was "
            "submitted. Please run intake again when you're ready.",
            file=sys.stderr,
        )
        return None

    first_name = input_fn("\nChild's first name (used only in captions): ").strip()
    nickname = input_fn("Optional nickname (press Enter to skip): ").strip() or None

    print("\nPaste the story, then press Ctrl-D (EOF) to finish:")
    story_text = story_reader()

    try:
        return ParentSubmission(
            story_text=story_text,
            child_first_name=first_name,
            consent=consent,
            child_nickname=nickname,
        )
    except ValueError as exc:
        print(f"\nerror: {exc}. Nothing was submitted.", file=sys.stderr)
        return None


def _ask_yes_no(input_fn: Callable[[str], str], prompt: str) -> bool:
    """Ask a yes/no question; anything but an explicit yes is treated as no.

    Default-deny: a blank answer, EOF, or anything other than y/yes does not
    grant the consent.
    """
    try:
        answer = input_fn(f"{prompt} (y/n) ").strip().lower()
    except EOFError:
        return False
    return answer in {"y", "yes"}


def _maybe_render(
    args: argparse.Namespace,
    *,
    store: StoryStore,
    story_id: str,
    script: dict[str, Any],
    mapping: NameMapping,
) -> int:
    """Render the review-gated draft animation unless ``--no-render`` was set."""
    if args.no_render:
        print("\nScene script stored. Skipped rendering (--no-render).")
        return 0

    try:
        narration = _load_voice(args.voice)
    except ValueError as exc:
        print(f"error: invalid --voice template: {exc}", file=sys.stderr)
        return 2

    try:
        renderer = _load_default_renderer()
        media_path = _render_draft(
            renderer=renderer,
            store=store,
            story_id=story_id,
            script=script,
            mapping=mapping,
            extra_out=args.out,
            narration=narration,
        )
    except (RuntimeError, KathaiChithiramError, VideoError) as exc:
        print(f"error: render failed: {exc}", file=sys.stderr)
        print("(the scene script was generated and stored; only rendering failed)", file=sys.stderr)
        return 2

    print(f"\nDraft animation: {media_path}")
    if narration is not None:
        print("(with local narration audio)")
    if args.out is not None:
        print(f"Copy written to: {args.out}")
    print(
        "\n⚠  DRAFT — a human must review this animation (and the captioned "
        "scene script) before it is shown to a child. It is NOT marked delivered."
    )
    print(f"   Review it with:  kc review {story_id} --show")
    return 0


def _read_story(source: str) -> str:
    """Read story text from a file path, or from stdin when ``source`` is '-'.

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
    puts the repo root on ``sys.path`` before importing.

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


def _load_voice(spec: str | None) -> NarrationSynthesizer | None:
    """Build a local narration voice from a ``--voice`` command template.

    Args:
        spec: The command template (with ``{out}``/``{text}`` tokens), or ``None``
            for a silent render.

    Returns:
        A :class:`CliTtsSynthesizer` for ``spec``, or ``None`` when no voice was
        requested.

    Raises:
        ValueError: If ``spec`` is empty/blank or omits the required ``{out}`` token
            (surfaced to the user as a usage error).
    """
    if spec is None:
        return None
    return CliTtsSynthesizer(shlex.split(spec))


def _render_draft(
    *,
    renderer: SceneScriptRenderer,
    store: StoryStore,
    story_id: str,
    script: dict[str, Any],
    mapping: NameMapping,
    extra_out: Path | None,
    narration: NarrationSynthesizer | None = None,
) -> Path:
    """Render a guarded draft animation through the shared video seam and file it.

    Routes through :func:`generate_story_video` so ``kc`` produces its draft on the
    same wegofwd-video path as every other consumer: the brief is capability-checked
    against the renderer's limits, the media is sealed at rest through the store
    (KC-5), and a provenance stamp (provider/model/seed/contract versions) is
    persisted alongside it. When ``narration`` is given, its track is synthesized
    in-process and muxed into the media. The optional ``--out`` copy is the
    decrypted, playable bytes read back from the store, not the sealed on-disk file.
    """
    result = generate_story_video(
        renderer=renderer,
        script=script,
        store=store,
        story_id=story_id,
        mapping=mapping,
        narration=narration,
        filename=_DRAFT_MEDIA_FILENAME,
    )
    if extra_out is not None:
        extra_out.parent.mkdir(parents=True, exist_ok=True)
        extra_out.write_bytes(store.read_media(story_id, _DRAFT_MEDIA_FILENAME))
    return result.media_path


def _open_store(store_root: Path, *, warn_if_plaintext: bool = False) -> StoryArtifactStore | None:
    """Open the artifact store, enabling at-rest encryption when configured.

    Reads the storage key from the environment (KC-5). Returns ``None`` (after
    printing why) if a key is set but invalid, so the caller can exit cleanly.

    Args:
        store_root: Base directory for the store.
        warn_if_plaintext: If ``True`` and no key is configured, print a note that
            artifacts will be written unencrypted.
    """
    from kathai_chithiram.errors import EncryptionKeyError
    from kathai_chithiram.storage import STORAGE_KEY_ENV, load_cipher_from_env

    try:
        cipher = load_cipher_from_env()
    except EncryptionKeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return None
    if cipher is None and warn_if_plaintext:
        print(
            f"note: {STORAGE_KEY_ENV} is not set — stored artifacts will NOT be "
            "encrypted at rest. Set it for any real data (PRIVACY.md §7).",
            file=sys.stderr,
        )
    return StoryArtifactStore(store_root, cipher=cipher)


#: Env var naming the acting principal; defaults to a single local operator identity.
_PRINCIPAL_ENV = "KC_PRINCIPAL"
_LOCAL_PRINCIPAL_ID = "local-operator"
#: Cross-story access audit log, kept at the store root (log-safe: opaque ids only).
_AUDIT_LOG_FILE = "access_audit.jsonl"


def _resolve_principal() -> Principal | None:
    """Resolve the acting principal for access control (ADR-004, KC-11).

    Reads ``KC_PRINCIPAL`` (an opaque id) and defaults to a single local operator
    identity, so single-user CLI use works without configuration while every store
    access still goes through the authorization checkpoint. Returns ``None`` (after
    printing why) if the configured id is invalid.
    """
    raw = os.environ.get(_PRINCIPAL_ENV, "").strip() or _LOCAL_PRINCIPAL_ID
    try:
        return Principal(raw)
    except ValueError as exc:
        print(f"error: invalid {_PRINCIPAL_ENV}: {exc}", file=sys.stderr)
        return None


def _open_guarded_store(
    store_root: Path, *, warn_if_plaintext: bool = False
) -> GuardedStore | None:
    """Open the store and bind the acting principal, enforcing access (ADR-004).

    Returns ``None`` (after printing why) if the store key or the principal is
    misconfigured, so the caller can exit cleanly.
    """
    store = _open_store(store_root, warn_if_plaintext=warn_if_plaintext)
    if store is None:
        return None
    principal = _resolve_principal()
    if principal is None:
        return None
    audit = JsonlAuditSink(store_root / _AUDIT_LOG_FILE)
    return GuardedStore(store, principal, audit=audit)


def _build_anthropic_provider(*, model: str, effort: str) -> LLMProvider | None:
    """Construct the ZDR-keyed provider, printing a friendly error on failure.

    Story text about a child may only be sent with a dedicated no-training /
    zero-retention credential (KC-6), so this resolves the ZDR key and fails
    closed if it is absent — it never falls back to the ambient
    ``ANTHROPIC_API_KEY``.
    """
    from kathai_chithiram.errors import KathaiChithiramError
    from kathai_chithiram.wegofwd_llm.anthropic_provider import build_zdr_provider

    try:
        return build_zdr_provider(model=model, effort=effort)
    except KathaiChithiramError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return None


def _print_summary(*, story_id: str, store: StoryStore, generated: Any) -> None:
    """Print a console summary using the token form (no real name)."""
    script = generated.script
    print(f"story_id: {story_id}")
    print(f"stored under: {store.story_dir(story_id)}")
    print(f"generation attempts: {generated.attempts}")
    print(
        f"title: {script['title']}  |  scenes: {len(script['scenes'])}  |  "
        f"{script['total_duration_s']}s @ {script['fps']}fps  |  {script['locale']}"
    )
    print("scenes (child shown as token; name appears only in the rendered video):")
    for scene in script["scenes"]:
        print(f"  {scene['index']}. [{scene['duration_s']}s] {scene['narration']}")


if __name__ == "__main__":
    raise SystemExit(main())
