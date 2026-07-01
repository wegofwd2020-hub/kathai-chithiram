"""The identity seam — authenticate a credential to a :class:`Principal` (ADR-004 D3).

Identity is the one deployment-dependent part of access control, so it lives behind a
provider-agnostic seam (like ``LLMProvider`` for the LLM and ``StorageCipher`` for
crypto): the authorization model (:mod:`kathai_chithiram.access.policy`) is complete
and enforced regardless of *where* identities come from. This module ships a concrete
:class:`LocalIdentityProvider` for the single-machine prototype; a networked identity
provider (e.g. OIDC) is a future concrete behind the same :class:`IdentityProvider`
protocol, and swapping it does not touch the policy or the store boundary.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from kathai_chithiram.access.principal import Principal
from kathai_chithiram.errors import AccessDeniedError

__all__ = ["IdentityProvider", "LocalIdentityProvider"]


@runtime_checkable
class IdentityProvider(Protocol):
    """Authenticates an opaque credential to a :class:`Principal`.

    Implementations must **fail closed**: an unknown, empty, or invalid credential
    raises :class:`~kathai_chithiram.errors.AccessDeniedError` rather than returning a
    principal or ``None``.
    """

    def authenticate(self, credential: str) -> Principal:
        """Return the principal a credential authenticates to, or raise.

        Raises:
            AccessDeniedError: If the credential authenticates to no principal.
        """
        ...


class LocalIdentityProvider:
    """A concrete identity provider backed by an in-memory credential table.

    For a single-machine deployment: credentials (opaque tokens supplied from
    configuration, never committed) map to principals. No credential material or
    principal name is ever logged. This is genuine enforcement for one machine — it
    is **not** a substitute for network authentication (ADR-004).

    Args:
        credentials: Map of opaque credential token to the :class:`Principal` it
            authenticates. Copied defensively so later mutation of the caller's map
            cannot change who authenticates.

    Raises:
        ValueError: If a credential token is empty.
    """

    def __init__(self, credentials: Mapping[str, Principal]) -> None:
        for token in credentials:
            if not token:
                raise ValueError("credential token must be non-empty")
        self._credentials: dict[str, Principal] = dict(credentials)

    def authenticate(self, credential: str) -> Principal:
        """Return the principal for ``credential``, or raise if unknown.

        Args:
            credential: The opaque credential token presented by the caller.

        Returns:
            The authenticated :class:`Principal`.

        Raises:
            AccessDeniedError: If the credential is empty or maps to no principal.
                The error carries no credential material (PRIVACY.md §6).
        """
        principal = self._credentials.get(credential) if credential else None
        if principal is None:
            raise AccessDeniedError("authenticate", "unknown or empty credential")
        return principal
