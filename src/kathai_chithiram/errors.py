"""Domain-specific errors for Kathai Chithiram.

Per WeGoFwd standards, code raises explicit domain errors with context rather
than swallowing exceptions or surfacing bare ``Exception``. Error messages in
this module are constructed to be **safe to log**: they never embed raw story
text, captions, narration, or a child's real name (see ``PRIVACY.md`` §6 and
``docs/CONTENT_SAFETY.md`` §5).
"""

from __future__ import annotations

__all__ = [
    "AccessDeniedError",
    "ConsentError",
    "DecryptionError",
    "DeletionError",
    "EncryptionKeyError",
    "IdentifierLeakError",
    "KathaiChithiramError",
    "PeopleError",
    "PolicyError",
    "ProviderConfigError",
    "ProviderResponseError",
    "ProviderUnavailableError",
    "RenderSafetyError",
    "ReviewError",
    "SuggestionError",
    "SceneScriptGenerationError",
    "SceneScriptInvalidError",
    "StoryNotFoundError",
    "UnsupportedSchemaVersionError",
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


class ProviderUnavailableError(KathaiChithiramError):
    """A concrete provider could not be constructed because a dependency is absent.

    Raised when wiring an optional provider whose SDK is not installed (e.g. the
    Anthropic provider without the ``[generation]`` extra). The message names the
    missing dependency and how to install it — never any story text.

    Args:
        provider_id: Identifier of the provider that could not be built.
        reason: What is missing and how to resolve it (no raw story text).
    """

    def __init__(self, provider_id: str, reason: str) -> None:
        self.provider_id = provider_id
        self.reason = reason
        super().__init__(f"provider '{provider_id}' unavailable: {reason}")


class ProviderResponseError(KathaiChithiramError):
    """A provider returned a response that cannot be used as generation output.

    Distinct from :class:`ProviderConfigError` (a *pre-dispatch* refusal): this
    is raised *after* a call returns, when the reply is a safety refusal or
    carries no usable text. The message names the provider and the failure mode
    only — it never echoes the provider's content, which may derive from story
    text.

    Args:
        provider_id: Identifier of the provider (model) that produced the reply.
        reason: Why the reply is unusable (e.g. ``"safety refusal"``). No raw
            story text.
    """

    def __init__(self, provider_id: str, reason: str) -> None:
        self.provider_id = provider_id
        self.reason = reason
        super().__init__(f"provider '{provider_id}' returned an unusable response: {reason}")


class SceneScriptGenerationError(KathaiChithiramError):
    """Generation could not produce a contract-valid scene script.

    Raised when a provider reply cannot be parsed as a scene script, or when no
    attempt produced a script that passes :func:`validate_scene_script` within
    the allowed number of tries. Like :class:`SceneScriptInvalidError`, it
    carries a stable ``rule`` id and a log-safe ``detail`` (no captions,
    narration, or names — only rule ids, counts, and the attempt budget).

    Args:
        rule: Stable identifier of the failure, e.g.
            ``"generation.unparseable"`` or ``"generation.exhausted"``.
        detail: Human-readable explanation that MUST NOT contain raw story text.
        attempts: How many generation attempts were made, when applicable.

    Raises:
        ValueError: If ``rule`` is empty.
    """

    def __init__(self, rule: str, detail: str, *, attempts: int | None = None) -> None:
        if not rule:
            raise ValueError("rule must be a non-empty rule identifier")
        self.rule = rule
        self.detail = detail
        self.attempts = attempts
        suffix = f" after {attempts} attempt(s)" if attempts is not None else ""
        super().__init__(f"[{rule}]{suffix}: {detail}")


class ConsentError(KathaiChithiramError):
    """A parent's submission lacks a consent required to process it.

    Intake is the legal-basis checkpoint (PRIVACY.md §2 parental control, §8
    consent capture): a story may only be processed once the parent/guardian has
    granted every required consent. Raised before any story text is generated,
    stored, or sent to a provider. The message names which consent is missing —
    never any story text.

    Args:
        missing: The consents that were not granted (stable keys, e.g.
            ``"is_guardian"``).
    """

    def __init__(self, missing: tuple[str, ...]) -> None:
        self.missing = missing
        joined = ", ".join(missing) if missing else "(none)"
        super().__init__(f"required consent not granted: {joined}")


class StoryNotFoundError(KathaiChithiramError):
    """A story id was requested but no artifacts exist for it.

    Args:
        story_id: The id that was not found. A story id is an opaque
            identifier, not a name, so it is safe to include.
    """

    def __init__(self, story_id: str) -> None:
        self.story_id = story_id
        super().__init__(f"no story found for id {story_id!r}")


class PeopleError(KathaiChithiramError):
    """A people/family registry operation was invalid (ADR-005 parts b/c).

    Raised for an unknown, duplicate, or cross-family record, or a missing parental
    consent. Carries only opaque ids — never a name or a date of birth (the registry
    stores neither).

    Args:
        reason: What was wrong (opaque ids only, no personal data).
    """

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class EncryptionKeyError(KathaiChithiramError):
    """The at-rest encryption key is missing, malformed, or the wrong size.

    Raised when building the storage cipher from configuration (KC-5,
    PRIVACY.md §7): a deployment that opts into encryption must supply a valid
    key. The message describes the problem — never the key material or any story
    text.

    Args:
        reason: What is wrong with the configured key (no secret material).
    """

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"storage encryption key error: {reason}")


class DecryptionError(KathaiChithiramError):
    """A stored artifact could not be decrypted or failed authentication.

    Raised when reading an encrypted artifact whose ciphertext is corrupt, was
    tampered with, or was written under a different key (KC-5). Decryption
    **fails closed**: it never returns partial/garbled bytes and never falls
    back to treating ciphertext as plaintext. The message names the artifact
    (safe relative path) only — never the key or any decrypted content.

    Args:
        artifact: A safe identifier for the artifact that failed (e.g. a file
            name), with no secret or story content.
    """

    def __init__(self, artifact: str) -> None:
        self.artifact = artifact
        super().__init__(
            f"could not decrypt stored artifact {artifact!r}: wrong key or corrupt/"
            "tampered ciphertext"
        )


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


class ReviewError(KathaiChithiramError):
    """A human-review decision could not be recorded, or is not permitted.

    The review step is the gate between a rendered *draft* and a *delivered*
    animation (CONTENT_SAFETY.md §6): a person inspects the draft and either
    approves it (which marks it delivered) or rejects it (which leaves it for the
    retention sweep). Raised when a decision is malformed (no reviewer, a
    rejection with no reason) or not allowed yet (approving a story that has no
    rendered draft to review). The message names the story (safe opaque id) and
    the reason — never any story text.

    Args:
        story_id: The story whose review failed (safe opaque id).
        reason: What was wrong with the decision, with no raw story text.
    """

    def __init__(self, story_id: str, reason: str) -> None:
        self.story_id = story_id
        self.reason = reason
        super().__init__(f"review of story {story_id!r} failed: {reason}")


class SuggestionError(KathaiChithiramError):
    """A premise-suggestion review action is malformed or not permitted.

    The M1 progress track keeps a therapist in the loop (ADR-002 Decision 7.3): a
    suggestion is recorded, then a reviewer explicitly accepts / edits / dismisses
    it. Raised when a decision targets an unknown suggestion or one already
    decided. The message names the suggestion (opaque id) and the reason — never
    any child data.

    Args:
        suggestion_id: The suggestion the action targeted (safe opaque id).
        reason: What was wrong with the action, with no child data.
    """

    def __init__(self, suggestion_id: str, reason: str) -> None:
        self.suggestion_id = suggestion_id
        self.reason = reason
        super().__init__(f"suggestion {suggestion_id!r}: {reason}")


class AccessDeniedError(KathaiChithiramError):
    """A principal was denied access to child content, or could not be authenticated.

    The access-control layer (ADR-004, KC-11) is deny-by-default: a principal with no
    authorized relationship to a story — or a credential that authenticates to no
    principal — is refused before any artifact is read, decrypted, or written. It
    **fails closed**: a denied access never returns partial content. The message names
    the principal (opaque id), the story (opaque id), and the action — never any story
    text, caption, or name (PRIVACY.md §6).

    Args:
        action: The attempted action (e.g. ``"read_content"``, ``"authenticate"``).
        reason: Why it was denied, with no child data.
        principal_id: The principal that was refused, if known (safe opaque id).
        story_id: The story involved, if applicable (safe opaque id).
    """

    def __init__(
        self,
        action: str,
        reason: str,
        *,
        principal_id: str | None = None,
        story_id: str | None = None,
    ) -> None:
        self.action = action
        self.reason = reason
        self.principal_id = principal_id
        self.story_id = story_id
        who = repr(principal_id) if principal_id is not None else "(unauthenticated)"
        where = f" story={story_id!r}" if story_id is not None else ""
        super().__init__(f"access denied for {who} action={action!r}{where}: {reason}")


class PolicyError(KathaiChithiramError):
    """A progress policy could not be applied to the given evidence.

    The M1 progress engine (ADR-003) interprets a collaborator-authored
    :class:`~kathai_chithiram.progress.policy.ProgressPolicy` over an evidence
    bundle. Raised when the two are mismatched — e.g. the evidence was gathered
    over a different window than the policy calibrates for, so its thresholds would
    be applied to the wrong number of sessions. The message names the policy
    (opaque id) and the mismatch — never any child data.

    Args:
        policy_id: The policy that could not be applied (safe opaque id).
        reason: Why it could not be applied, with no child data.
    """

    def __init__(self, policy_id: str, reason: str) -> None:
        self.policy_id = policy_id
        self.reason = reason
        super().__init__(f"progress policy {policy_id!r} cannot be applied: {reason}")


class RenderSafetyError(KathaiChithiramError):
    """A render output or configuration violates a technical safety limit.

    These are the render-time guards of ``docs/CONTENT_SAFETY.md`` §2/§5:
    frame-rate, flashing / high-contrast oscillation (seizure safety), and audio
    levels. Output that trips a guard must not reach a child.

    Args:
        rule: Stable identifier of the violated guard, e.g.
            ``"render.flash_rate"``.
        detail: Explanation with measured values (numbers only, no story text).
    """

    def __init__(self, rule: str, detail: str) -> None:
        if not rule:
            raise ValueError("rule must be a non-empty rule identifier")
        self.rule = rule
        self.detail = detail
        super().__init__(f"[{rule}]: {detail}")


class UnsupportedSchemaVersionError(KathaiChithiramError):
    """A renderer was handed a scene script whose MAJOR version it can't render.

    The contract has renderers declare the schema MAJOR versions they support
    (``docs/SCENE_SCRIPT_CONTRACT.md`` §4); this is raised when a script falls
    outside that set.

    Args:
        renderer_name: The renderer that rejected the script.
        major: The script's schema MAJOR version.
        supported: The MAJOR versions the renderer supports.
    """

    def __init__(self, renderer_name: str, major: int, supported: list[int]) -> None:
        self.renderer_name = renderer_name
        self.major = major
        self.supported = supported
        super().__init__(
            f"renderer {renderer_name!r} does not support schema MAJOR {major} "
            f"(supports {supported})"
        )
