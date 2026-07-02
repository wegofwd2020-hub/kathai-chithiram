"""Operator access control for stored child content (ADR-004, KC-11, DPIA R10).

The store's persistence layer is keyed by ``story_id`` and carries no notion of a
caller. This package adds the missing authorization boundary: an authenticated
:class:`Principal`, a deny-by-default :class:`AccessPolicy` over per-story
:class:`StoryGrants`, a provider-agnostic :class:`IdentityProvider` seam (with a
concrete :class:`LocalIdentityProvider`), and a log-safe :class:`AuditSink`.

This package is the **model** — pure decision logic, identity, and audit primitives.
Wiring it into the `StoryArtifactStore` boundary (threading a principal through the
content-bearing methods, recording ownership, enforcing before any read/decrypt/write)
is a separate step; keeping the model standalone makes it unit-testable in isolation.
Enforcement fails closed via :class:`~kathai_chithiram.errors.AccessDeniedError`.
"""

from __future__ import annotations

from kathai_chithiram.access.audit import (
    AccessEvent,
    AccessOutcome,
    AuditSink,
    InMemoryAuditSink,
    JsonlAuditSink,
)
from kathai_chithiram.access.guarded_store import GuardedStore
from kathai_chithiram.access.identity import IdentityProvider, LocalIdentityProvider
from kathai_chithiram.access.policy import (
    AccessPolicy,
    Action,
    ChildGrants,
    ChildGrantsSource,
    Grants,
    StoryGrants,
)
from kathai_chithiram.access.principal import Principal, Role

__all__ = [
    "AccessEvent",
    "AccessOutcome",
    "AccessPolicy",
    "Action",
    "AuditSink",
    "GuardedStore",
    "IdentityProvider",
    "InMemoryAuditSink",
    "JsonlAuditSink",
    "LocalIdentityProvider",
    "Principal",
    "Role",
    "ChildGrants",
    "ChildGrantsSource",
    "Grants",
    "StoryGrants",
]
