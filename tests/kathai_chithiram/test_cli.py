"""Tests for the end-to-end CLI.

Driven with a scripted stub provider and ``--no-render`` so the wiring is
exercised without a network call or a heavy matplotlib render. The privacy and
review boundaries are the focus: the raw story (with the name) is stored, the
scene script is not (token only), the name never reaches the provider, and the
provider's privacy posture must be asserted before anything is sent.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from kathai_chithiram.cli import _cmd_intake, build_arg_parser, main
from kathai_chithiram.generation import EXAMPLE_SCENE_SCRIPT
from kathai_chithiram.wegofwd_llm.provider import LLMRequest, LLMResponse

CHILD = "Robin"
STORY = "Robin is scared of the dark. Robin turns on a light and feels calm."


@dataclass
class ScriptedProvider:
    """A fake provider returning one canned JSON reply, recording requests."""

    reply: str
    requests: list[LLMRequest] = field(default_factory=list)

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(text=self.reply)


def _provider() -> ScriptedProvider:
    return ScriptedProvider(reply=json.dumps(copy.deepcopy(EXAMPLE_SCENE_SCRIPT)))


def _write_story(tmp_path: Path) -> Path:
    story_file = tmp_path / "story.txt"
    story_file.write_text(STORY, encoding="utf-8")
    return story_file


def _argv(story_file: Path, store_root: Path, *extra: str) -> list[str]:
    return [
        "generate",
        str(story_file),
        "--child-name",
        CHILD,
        "--story-id",
        "test-story",
        "--store-root",
        str(store_root),
        *extra,
    ]


def test_happy_path_stores_story_and_scene_script(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    provider = _provider()
    code = main(
        _argv(_write_story(tmp_path), store_root, "--provider-no-train-zdr", "--no-render"),
        provider=provider,
    )
    assert code == 0

    story_dir = store_root / "test-story"
    # The raw story (which names the child) is stored as story.txt by design.
    assert (story_dir / "story.txt").read_text(encoding="utf-8") == STORY
    # The scene script must carry only the token — never the real name.
    script_text = (story_dir / "scene_script.json").read_text(encoding="utf-8")
    assert CHILD not in script_text
    assert "CHILD" in json.loads(script_text)["child_token"]


def test_child_name_never_reaches_provider(tmp_path: Path) -> None:
    provider = _provider()
    main(
        _argv(_write_story(tmp_path), tmp_path / "store", "--provider-no-train-zdr", "--no-render"),
        provider=provider,
    )
    sent = provider.requests[0].prompt
    assert CHILD not in sent
    assert "CHILD" in sent


def test_refuses_without_privacy_assertion(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    provider = _provider()
    # No --provider-no-train-zdr: generation must refuse before dispatch.
    code = main(
        _argv(_write_story(tmp_path), store_root, "--no-render"),
        provider=provider,
    )
    assert code == 2
    assert provider.requests == []  # nothing was sent
    assert not (store_root / "test-story").exists()  # nothing was stored


def test_missing_story_file_errors(tmp_path: Path) -> None:
    code = main(
        _argv(tmp_path / "does-not-exist.txt", tmp_path / "store", "--provider-no-train-zdr"),
        provider=_provider(),
    )
    assert code == 2


def test_empty_story_errors(tmp_path: Path) -> None:
    empty = tmp_path / "empty.txt"
    empty.write_text("   \n", encoding="utf-8")
    code = main(
        _argv(empty, tmp_path / "store", "--provider-no-train-zdr"),
        provider=_provider(),
    )
    assert code == 2


# --- intake subcommand ---------------------------------------------------------


def _scripted_input(answers: list[str]) -> Callable[[str], str]:
    it = iter(answers)

    def _input(_prompt: str) -> str:
        return next(it)

    return _input


def _intake_args(store_root: Path) -> object:
    return build_arg_parser().parse_args(
        ["intake", "--story-id", "intake-story", "--store-root", str(store_root), "--no-render"]
    )


def test_intake_happy_path_records_consent(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    provider = _provider()
    code = _cmd_intake(
        _intake_args(store_root),
        provider=provider,
        input_fn=_scripted_input(["y", "y", "y", CHILD, ""]),  # 3 consents, name, no nickname
        story_reader=lambda: STORY,
    )
    assert code == 0

    story_dir = store_root / "intake-story"
    assert (story_dir / "story.txt").read_text(encoding="utf-8") == STORY
    # Scene script carries the token only.
    assert CHILD not in (story_dir / "scene_script.json").read_text(encoding="utf-8")
    # The intake record proves consent and carries no story text or name.
    intake = json.loads((story_dir / "intake.json").read_text(encoding="utf-8"))
    assert intake["consent"] == {
        "is_guardian": True,
        "ai_processing": True,
        "human_review_ack": True,
    }
    assert CHILD not in json.dumps(intake)
    assert "dark" not in json.dumps(intake)  # no story fragment leaked
    # Name was stripped before the provider saw it.
    assert CHILD not in provider.requests[0].prompt


def test_intake_declined_consent_submits_nothing(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    provider = _provider()
    code = _cmd_intake(
        _intake_args(store_root),
        provider=provider,
        input_fn=_scripted_input(["y", "n", "y", CHILD, ""]),  # consent #2 declined
        story_reader=lambda: STORY,
    )
    assert code == 2
    assert provider.requests == []  # nothing was generated
    assert not (store_root / "intake-story").exists()  # nothing was stored


def test_intake_shows_privacy_notice_before_consent(tmp_path: Path, capsys) -> None:
    from kathai_chithiram.intake import PRIVACY_NOTICE_DOC, PRIVACY_NOTICE_VERSION

    store_root = tmp_path / "store"
    _cmd_intake(
        _intake_args(store_root),
        provider=_provider(),
        input_fn=_scripted_input(["y", "y", "y", CHILD, ""]),
        story_reader=lambda: STORY,
    )
    out = capsys.readouterr().out
    # The notice (version + doc pointer) is shown, and before the consent prompt.
    assert PRIVACY_NOTICE_VERSION in out
    assert PRIVACY_NOTICE_DOC in out
    assert out.index(PRIVACY_NOTICE_DOC) < out.index("please confirm")


# --- review subcommand ---------------------------------------------------------


def _seed_rendered_story(store_root: Path, story_id: str = "review-story") -> None:
    """Create a story with a scene script and a rendered draft, ready to review."""
    from datetime import datetime, timezone

    from kathai_chithiram.storage import StoryArtifactStore

    store = StoryArtifactStore(store_root)
    store.create_story(
        story_id, created_at=datetime(2026, 6, 1, tzinfo=timezone.utc), story_text=STORY
    )
    store.write_scene_script(story_id, copy.deepcopy(EXAMPLE_SCENE_SCRIPT))
    store.add_media(story_id, "animation.mp4", b"\x00mp4\x01")


def _review_argv(store_root: Path, *extra: str) -> list[str]:
    return ["review", "review-story", "--store-root", str(store_root), *extra]


def test_review_show_lists_the_draft(tmp_path: Path, capsys) -> None:
    store_root = tmp_path / "store"
    _seed_rendered_story(store_root)
    code = main(_review_argv(store_root, "--show"))
    assert code == 0
    out = capsys.readouterr().out
    assert "animation.mp4" in out
    assert "delivered: False" in out


def test_review_approve_marks_delivered(tmp_path: Path) -> None:
    from kathai_chithiram.storage import StoryArtifactStore

    store_root = tmp_path / "store"
    _seed_rendered_story(store_root)
    code = main(_review_argv(store_root, "--approve", "--reviewer", "alex"))
    assert code == 0
    assert StoryArtifactStore(store_root).read_metadata("review-story").delivered is True


def test_review_approve_requires_reviewer(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    _seed_rendered_story(store_root)
    code = main(_review_argv(store_root, "--approve"))
    assert code == 2


def test_review_reject_without_reason_errors(tmp_path: Path) -> None:
    from kathai_chithiram.storage import StoryArtifactStore

    store_root = tmp_path / "store"
    _seed_rendered_story(store_root)
    code = main(_review_argv(store_root, "--reject", "--reviewer", "alex"))
    assert code == 2
    assert StoryArtifactStore(store_root).read_metadata("review-story").delivered is False


def test_review_missing_story_errors(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    code = main(["review", "ghost", "--store-root", str(store_root), "--show"])
    assert code == 2


# --- at-rest encryption (KC-5) -------------------------------------------------


def test_generate_encrypts_at_rest_when_key_set(tmp_path: Path, monkeypatch) -> None:
    from kathai_chithiram.storage import STORAGE_KEY_ENV, generate_key, load_cipher_from_env

    key = generate_key()
    monkeypatch.setenv(STORAGE_KEY_ENV, key)
    store_root = tmp_path / "store"
    code = main(
        _argv(_write_story(tmp_path), store_root, "--provider-no-train-zdr", "--no-render"),
        provider=_provider(),
    )
    assert code == 0

    # Raw story on disk is ciphertext, not the plaintext story.
    raw = (store_root / "test-story" / "story.txt").read_bytes()
    assert STORY.encode() not in raw
    # ...but it decrypts back with the key.
    cipher = load_cipher_from_env({STORAGE_KEY_ENV: key})
    from kathai_chithiram.storage import StoryArtifactStore

    encrypted = StoryArtifactStore(store_root, cipher=cipher)
    assert encrypted.read_scene_script("test-story")["title"]


def test_generate_bad_storage_key_exits(tmp_path: Path, monkeypatch) -> None:
    from kathai_chithiram.storage import STORAGE_KEY_ENV

    monkeypatch.setenv(STORAGE_KEY_ENV, "not-valid-base64 !!!")
    code = main(
        _argv(_write_story(tmp_path), tmp_path / "store", "--provider-no-train-zdr", "--no-render"),
        provider=_provider(),
    )
    assert code == 2


# --- ZDR / no-training credential (KC-6) ---------------------------------------


def test_generate_fails_closed_without_zdr_key(tmp_path: Path, monkeypatch) -> None:
    from kathai_chithiram.wegofwd_llm.anthropic_provider import ZDR_API_KEY_ENV

    monkeypatch.delenv(ZDR_API_KEY_ENV, raising=False)
    store_root = tmp_path / "store"
    # No provider injected -> the CLI must resolve the dedicated ZDR key and,
    # finding none, refuse rather than fall back to a general key.
    code = main(
        _argv(_write_story(tmp_path), store_root, "--provider-no-train-zdr", "--no-render")
    )
    assert code == 2
    assert not (store_root / "test-story").exists()  # nothing generated or stored
