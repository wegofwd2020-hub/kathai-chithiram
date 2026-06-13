"""Domain-specific errors for Kathai Chithiram.

Per WeGoFwd standards, code raises explicit domain errors with context rather
than swallowing exceptions or surfacing bare ``Exception``. Error messages in
this module are constructed to be **safe to log**: they never embed raw story
text, captions, narration, or a child's real name (see ``PRIVACY.md`` §6 and
``docs/CONTENT_SAFETY.md`` §5).
"""

from __future__ import annotations

__all__ = [
    "DeletionError",
    "IdentifierLeakError",
    "KathaiChithiramError",
    "ProviderConfigError",
    "SceneScriptInvalidError",
    "StoryNotFoundError",
]


class KathaiChithiramError(Exception):
    """Base class for all errors raised by this package.

    Catch this to handle any Kathai Chithiram failure without resorting to a
    blind ``except Exception``.
    """


class SceneScriptInvalidError(KathaiChithiramError):
    """A scene script failed validation and must not be rendered.

    The error identifies *which* rule failed and *where*, but deliberately
    carries no raw story content so it is safe to log.

    Args:
        rule: Stable identifier of the violated rule, e.g.
            ``"scene.duration_s.out_of_range"``. Used by callers and logs to
            branch on the failure without parsing prose.
        detail: Human-readable explanation that MUST NOT contain raw story
            text, captions, narration, or a real name. Lengths and counts are
            fine; verbatim content is not.
        scene_index: 1-based index of the offending scene, when applicable.
        field: Name of the offending field, when applicable.

    Raises:
        ValueError: If ``rule`` is empty.
    """

    def __init__(
        self,
        rule: str,
        detail: str,
        *,
        scene_index: int | None = None,
        field: str | None = None,
    ) -> None:
        if not rule:
            raise ValueError("rule must be a non-empty rule identifier")
        self.rule = rule
        self.detail = detail
        self.scene_index = scene_index
        self.field = field

        location = ""
        if scene_index is not None:
            location += f" scene={scene_index}"
        if field is not None:
            location += f" field={field}"
        super().__init__(f"[{rule}]{location}: {detail}")


class IdentifierLeakError(KathaiChithiramError):
    """An outbound payload still contained a child identifier after minimization.

    Raised by the ``wegofwd-llm`` seam as a hard stop before anything is sent to
    a provider: pseudonymization is expected to have removed every identifier,
    so a residual match is a defect, not a recoverable condition. The message
    carries the count and length of the leak — never the identifier itself
    (PRIVACY.md §6).

    Args:
        residual_count: How many identifier occurrences remained.
    """

    def __init__(self, residual_count: int) -> None:
        self.residual_count = residual_count
        super().__init__(
            f"outbound payload still contains {residual_count} child-identifier "
            "occurrence(s) after pseudonymization; refusing to send"
        )


class ProviderConfigError(KathaiChithiramError):
    """The LLM provider configuration does not meet the privacy bar.

    Story text about a child must only go to a provider configured for
    no-training and zero-retention (PRIVACY.md §6). Raised before dispatch when
    that guarantee is absent.

    Args:
        provider_id: Identifier of the offending provider configuration.
        reason: Why the configuration was rejected (no raw story text).
    """

    def __init__(self, provider_id: str, reason: str) -> None:
        self.provider_id = provider_id
        self.reason = reason
        super().__init__(f"provider '{provider_id}' rejected: {reason}")


class StoryNotFoundError(KathaiChithiramError):
    """A story id was requested but no artifacts exist for it.

    Args:
        story_id: The id that was not found. A story id is an opaque
            identifier, not a name, so it is safe to include.
    """

    def __init__(self, story_id: str) -> None:
        self.story_id = story_id
        super().__init__(f"no story found for id {story_id!r}")


class DeletionError(KathaiChithiramError):
    """A hard-delete could not be completed or could not be verified.

    Raised when removal fails or when artifacts remain after a delete — the
    latter is critical, since a partial delete of child story content must
    never pass silently (PRIVACY.md §5).

    Args:
        story_id: The story whose deletion failed (safe opaque id).
        reason: What went wrong, with no raw story text.
    """

    def __init__(self, story_id: str, reason: str) -> None:
        self.story_id = story_id
        self.reason = reason
        super().__init__(f"deletion of story {story_id!r} failed: {reason}")
