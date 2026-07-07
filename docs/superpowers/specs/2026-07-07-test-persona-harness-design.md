# Test-persona harness — design

**Date:** 2026-07-07 · **Status:** approved (brainstorm) · **Owner:** WeGoFwd2020

## Problem

The owner holds three personal email accounts and wants a stable, reusable set of
test personas — parent / child / therapist — that can be seeded across test runs and
also point at those real inboxes for the owner's own manual end-to-end checks (e.g.
guardian-delivery of a rendered animation).

Two constraints make this non-trivial:

1. **The `people` domain model has no email field, by design.** `models.py` stores
   opaque ids + a coarse `AgeBand` only; no names, no DOB (data minimization,
   DPIA addendum A8 / Art. 5(1)(c)). Email is not — and will not become — a domain field.
2. **Real personal data must never be committed.** `.gitignore` already blocks story
   data, `.env`, `*.key`, `secrets/`; CLAUDE.md forbids real data in tests/fixtures.
   The repo is on GitHub, so a real address in a committed fixture is leaked PII and
   git history is hard to scrub.

Separately, **email-as-login is an open DPO gate** — DPIA item **A4.2 (account-data
lawful basis)** is unruled and unbuilt (`docs/STATE_OF_PLAY.md`). Building real
email-based local accounts now would cross that gate. This design deliberately does
**not**: it adds a **test-only** persona layer and no production personal-data surface.

## Scope

**In:** a synthetic, committed persona-fixture layer under `tests/`, with builders that
assemble a coherent family + consent + child-scoped grants, plus a resolver that lets
the owner overlay his three real inboxes from a git-ignored local file.

**Out:** any production accounts/login/email code in `src/`; any storage of real emails
in committed code; the A4.2 lawful-basis work. Those remain gated.

## Architecture

Everything lives test-side. Nothing is added to `src/`.

```
tests/kathai_chithiram/people/
  mock_personas.py               # committed — synthetic personas + builders + resolver
  personas.local.example.json    # committed — template with fake values (documents shape)
  personas.local.json            # GIT-IGNORED — owner's 3 real inboxes, local machine only
  test_mock_personas.py          # tests for the harness itself
```

Convention follows the existing mock modules: `tests/.../wegofwd_llm/mock_story.py`,
`tests/.../scene_script/mock_scripts.py`.

## Components

### 1. `Persona` (test-only dataclass)

Wraps a domain object plus test-only metadata. The domain object is unchanged; the
email handle lives only here, never on `Parent`/`Child`/`Therapist`.

```
@dataclass(frozen=True)
class Persona:
    key: str            # "parent" | "child" | "therapist" — the override lookup key
    principal_id: str   # opaque id used in the domain layer
    login_handle: str   # email-shaped; @example.test placeholder by default
```

### 2. Three synthetic personas (one family)

- `PARENT` — builds a `Parent`; handle `parent@example.test`
- `CHILD` — builds a `Child` (age band `AGE_6_8`); handle `child@example.test`
  (kept for guardian-delivery E2E — the child does not log in; the handle addresses
  the guardian's inbox)
- `THERAPIST` — builds a `Therapist`; handle `therapist@example.test`

All ids are stable opaque strings (e.g. `fam-mock-001`, `parent-mock-001`) so seeds are
reproducible across runs.

### 3. Builders

Mirror `mock_story()` — one call returns a fully wired object:

- `mock_family() -> Family` — the family value object.
- `mock_registry() -> PeopleRegistry` — a registry with the family, child, therapist
  added; therapist assigned to the child (`assign(child_id, principal_id, Role.THERAPIST)`);
  `ParentalConsent` recorded (`record_consent`). Any test needing a consent-gated,
  grant-wired family gets it in one call.

### 4. Handle resolver with local override

- `resolve_handles(path: Path | None = None) -> dict[str, str]` maps persona `key` →
  effective login handle.
- Default: returns the committed `@example.test` placeholders.
- If a `personas.local.json` exists (default path, or the passed `path`), its values
  override the placeholders — for the owner's manual E2E only. CI, other clones, and
  default test runs never see it (git-ignored, absent).
- The local file supplies **handles only** (`{"parent": "...", "child": "...",
  "therapist": "..."}`). The resolver ignores any other keys, so no name/DOB can leak
  into domain objects (the model rejects them regardless).

## Safety guards

- Add `tests/kathai_chithiram/people/personas.local.json` to `.gitignore`.
- Commit `personas.local.example.json` with obviously-fake values (`you+parent@example.test`)
  documenting the expected shape.
- **Guard test:** scan `mock_personas.py` source and assert every `login_handle`
  literal ends in `@example.test` — the build fails if a real address is ever pasted
  into the committed file.
- Resolver whitelists the three known keys; unknown keys in the local file are dropped.

## Testing (CLAUDE.md: every new fn ships a test + mock data)

- `mock_family()` returns a valid `Family` (owner in members, ids well-formed).
- `mock_registry()` wires consent + therapist grant: `has_consent(child_id)` is true,
  and `child_grants` shows the therapist assigned.
- `resolve_handles()` with no local file returns the three `@example.test` placeholders.
- `resolve_handles(tmp_path/…)` with a written temp file overrides matching keys and
  drops unknown keys. (Tests never read the owner's real file.)
- Guard test: all committed handles are `@example.test`.

## Non-goals / future

- Production email login and the A4.2 lawful-basis ruling stay gated.
- If a real accounts layer is later built (post-DPO), these personas seed its tests,
  but the domain model still holds no email — the account↔principal mapping would be a
  separate, gated module.
