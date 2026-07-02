# R10 deployment boundary — what drops the residual from Medium to Low

**Status:** Design note (operational). **Owner:** WeGoFwd2020.
**Date:** 2026-07-02.
**Refs:** `docs/DPIA.md` R10 + §5 precondition 4; `docs/ADR_004_operator_access_control.md`;
`src/kathai_chithiram/access/` (`GuardedStore`, `IdentityProvider`, `AuditSink`);
`src/kathai_chithiram/storage/crypto.py` (KC-5).

> This is **not** an engineering ticket. R10's remaining gap is a *deployment
> topology*, not unwritten code — the code seams already exist (ADR-004). This note
> exists to unblock the ops conversation: it states precisely what boundary is
> required, why, and how to tell when R10 can be reassessed to Low.

## 1. The gap, stated precisely

R10 (an operator browses a child's story content) is currently **Medium inherent,
Medium residual**. The residual is Medium — not Low — for one reason:

> On the single-machine prototype, an operator with shell access can **bypass the
> `GuardedStore` entirely** by reading the store files directly. In-app
> authorization (ADR-004) only binds callers who go *through* the application.

At-rest encryption (KC-5/KC-10) does **not** close this: a running deployment holds
`KC_STORAGE_KEY`, so any process on the box that can read the key can decrypt. The
same operator who can bypass the app can typically read the key. KC-5 bounds a
*stolen disk*; ADR-004 bounds a *live caller of the app*; **neither bounds a live
operator with filesystem + key access.** That intersection is R10's residual.

So the residual rests today on **operator discipline + OS file permissions**, which
is exactly the "documented operational limit" ADR-004 chose to improve upon. In-app
enforcement pays off *fully* only where the filesystem bypass is removed.

## 2. The target

R10 → **Low** when a child's content can be reached **only** through the
`GuardedStore`-enforced API, authenticated as a real principal, on a system where
the person operating the service **cannot** read the raw store files or the master
key out of band. Concretely, all three must hold:

1. **No shared filesystem to the operator.** The store lives on a host/volume the
   operator does not have an interactive shell or file-read path to.
2. **Access is API-mediated and authenticated.** Reaching content means calling the
   guarded API as a principal an `IdentityProvider` authenticated — no "construct the
   store object and read" path is exposed to a human.
3. **The master key and audit log are held server-side**, outside the operator's
   reach, so decryption and the tamper-evident record are not operator-controllable.

## 3. The boundary design (reference deployment)

The point is a **process/network boundary** between *who operates the service* and
*where the data and key live*. One reference shape:

```
   parent / reviewer / therapist  ──HTTPS──▶  KC service  ──▶  GuardedStore ──▶  store volume
        (a Principal)                         (enforces          (per-story        (ciphertext;
                                               ADR-004)           authz + audit)     KC-5/KC-10)
                                                 ▲
                                    networked IdentityProvider (OIDC/…)
                                    master key from a secret manager
                                    audit sink → append-only central log
```

- **The service is the only reader of the store volume.** Operators administer the
  *service* (deploys, health), not the *data*: they have no shell on the data host
  and no mount of the store volume. "Operate the service" and "read a child's story"
  become different privileges held by different roles.
- **Identity moves to a networked provider** behind the existing `IdentityProvider`
  seam (ADR-004 D3). The `LocalIdentityProvider` (in-memory credential table) is
  replaced by a real IdP concrete; **the `AccessPolicy` and `GuardedStore` do not
  change** — that is the whole point of the seam.
- **The master key comes from a secret manager** injected into the service only
  (DPIA §5 precondition 3), not present as a file the operator can `cat`. Rotation
  uses the KC-10 `rewrap_story` procedure.
- **The audit sink becomes append-only/central** behind the existing `AuditSink`
  seam — today a `JsonlAuditSink` on the same disk (which a bypassing operator could
  edit); under the boundary it ships to a store the operator cannot rewrite, so
  "detect operator browsing" is trustworthy.

Nothing here contradicts the app: the CLI's `_open_guarded_store` already binds a
principal, wires the cipher, and attaches an audit sink. The boundary swaps the
*sources* (identity provider, key source, audit destination) behind seams already in
place, and relocates *where the store files live* relative to the operator.

## 4. Threat model — before vs. after

| Actor / path | Prototype (today) | Under the boundary |
|---|---|---|
| Authenticated principal via the app | Allowed per role (ADR-004), audited | Same — unchanged |
| Unrelated principal via the app | Denied, audited (fail closed) | Same — unchanged |
| Operator with shell on the data host | **Can bypass**: read/decrypt store files directly | No shell / no mount → **no bypass** |
| Operator reading `KC_STORAGE_KEY` off disk | **Possible** → can decrypt | Key is service-injected from a secret manager → **not readable** |
| Operator editing the audit log to hide browsing | **Possible** (local JSONL) | Append-only/central sink → **tamper-evident** |
| Stolen disk / backup | Ciphertext without the key (KC-5); crypto-shred on delete (KC-10) | Same — unchanged |

The boundary closes exactly the three rows that keep R10 at Medium; it changes
nothing about the app-mediated rows, which are already Low-grade controls.

## 5. Acceptance criteria for reassessing R10 → Low

R10's residual may be reassessed to **Low** when an operational review confirms all of:

- [ ] The store volume is **not** readable by any human operator role (no interactive
      shell, no mount, no backup-restore shortcut) — only the service process reads it.
- [ ] Content access is **only** via the authenticated, `GuardedStore`-enforced API;
      there is no exposed "construct store + read" path for a person.
- [ ] `KC_STORAGE_KEY` is delivered from a **secret manager** to the service process
      and is not present as an operator-readable file (also DPIA §5 precondition 3).
- [ ] A **networked `IdentityProvider`** authenticates principals; the
      `LocalIdentityProvider` is not the production identity source.
- [ ] The **audit sink** writes to an append-only/central store the operator cannot
      rewrite, and denied + allowed accesses are both captured.
- [ ] Break-glass / admin data access (if any) is itself authenticated, least-privilege,
      and audited — not an unlogged backdoor that reopens the bypass.

Until every box is checked, R10 stays **Medium** and a multi-user or networked launch
is not cleared (ADR-004 acceptance note; DPIA §5).

## 6. Out of scope / non-goals

- **In-app authorization** — already built (ADR-004/KC-11); this note does not change it.
- **At-rest crypto** — already built (KC-5/KC-10); the boundary governs *where the key
  lives*, not the cipher.
- **Choosing a specific IdP, orchestrator, or cloud** — deliberately left to the ops
  decision; this note fixes the *properties* the deployment must have, not the vendor.
- **New code** — none is required to satisfy §5; the concretes (networked IdP, central
  audit sink) land behind existing seams when the deployment exists (ADR-004 "Deferred").

## 7. One-line summary for the DPIA / ops

> R10 is Medium because a local operator can read the store files and key directly,
> bypassing the built-in access control. It becomes Low under a deployment where the
> service is the only reader of the data volume, the key comes from a secret manager,
> identity is a networked provider, and the audit log is append-only/central — all
> behind seams that already exist in code.
