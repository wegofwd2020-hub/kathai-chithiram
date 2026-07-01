"""The ``StoryStore`` protocol — the store surface the app's services depend on.

Services (intake, review) and the CLI operate over a story store, but they must work
against **either** the raw :class:`~kathai_chithiram.storage.store.StoryArtifactStore`
(in tests and non-access-controlled contexts) **or** the access-enforcing
``GuardedStore`` (in the app flows, ADR-004). Typing them against this structural
protocol lets a `GuardedStore` be substituted at the boundary without the persistence
layer importing the access package, and without changing the many tests that pass a
raw store — both satisfy it structurally.

Only the methods the services actually use are declared here; cross-story primitives
(``iter_story_ids``, ``artifact_paths``) are intentionally excluded — they are
system/operational operations outside the per-story authorization model (ADR-004).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from kathai_chithiram.storage.store import StoryMetadata

__all__ = ["StoryStore"]


@runtime_checkable
class StoryStore(Protocol):
    """The per-story read/write surface used by the intake, review, and CLI flows.

    Satisfied by both :class:`~kathai_chithiram.storage.store.StoryArtifactStore` and
    the access-enforcing ``GuardedStore``.
    """

    def create_story(
        self,
        story_id: str,
        *,
        created_at: datetime,
        story_text: str,
        delivered: bool = False,
    ) -> StoryMetadata: ...

    def write_scene_script(self, story_id: str, script: Mapping[str, Any]) -> None: ...

    def read_scene_script(self, story_id: str) -> dict[str, Any]: ...

    def write_intake_record(self, story_id: str, record: Mapping[str, Any]) -> None: ...

    def read_intake_record(self, story_id: str) -> dict[str, Any] | None: ...

    def write_review_record(self, story_id: str, record: Mapping[str, Any]) -> None: ...

    def read_review_record(self, story_id: str) -> dict[str, Any] | None: ...

    def read_metadata(self, story_id: str) -> StoryMetadata: ...

    def mark_delivered(self, story_id: str) -> StoryMetadata: ...

    def media_paths(self, story_id: str) -> list[Path]: ...

    def add_media(self, story_id: str, filename: str, data: bytes) -> Path: ...

    def story_dir(self, story_id: str) -> Path: ...

    def append_session_feedback(self, story_id: str, record: Mapping[str, Any]) -> None: ...

    def read_session_feedback(self, story_id: str) -> list[dict[str, Any]]: ...

    def append_progress_suggestion(self, story_id: str, record: Mapping[str, Any]) -> None: ...

    def read_progress_suggestions(self, story_id: str) -> list[dict[str, Any]]: ...
