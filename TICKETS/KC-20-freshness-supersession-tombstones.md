# KC-20 — Freshness: supersession, tombstones and retraction watch

**Labels:** P1, knowledge-base, safety
**Status:** 📋 Proposed — must exist before anything is served to a reader
**Refs:** `docs/ADR_011_corpus_rights_and_freshness.md` D4; `docs/ADR_010_retrieval_first_practice_assistant.md` D5

## Why
In this domain, **withdrawn guidance and retired clinical reports are more dangerous than
merely old content**, because they read as authoritative while being wrong. A rescinded OSEP
Dear Colleague letter, a retired AAP clinical report, a retracted study — each will be
retrieved, cited and believed, and the citation makes it *more* convincing, not less.

A retracted study surfaced without its retraction is the worst single output this system can
produce. Freshness here is therefore not a crawl schedule; it is a supersession problem, and
a re-crawl alone does not solve it because the superseding event often happens somewhere
other than the document itself.

## Acceptance criteria
- Every chunk carries a status: `current`, `superseded_by(<id>)`, `withdrawn`, `retracted`.
- A non-`current` chunk is **either suppressed from retrieval or served with its status
  stated** — never returned silently as current. This is the mechanism ADR-010 D5 depends on.
- Per-source re-ingestion cadence, running unattended:

  | Layer | Cadence |
  |---|---|
  | State Medicaid HCBS waivers (amendments file continuously between renewals) | Monthly, per-state diff |
  | State DD agency guidance, provider manuals, rate schedules | Quarterly, plus a pass after each legislative session |
  | Federal sub-regulatory guidance (OSEP DCLs, CMS bulletins, ACL notices) | Monthly, **with withdrawal detection** |
  | IDEA statute and 34 CFR Part 300 | Annually |
  | AAP clinical reports | Semi-annually, to catch **retirements** under the reaffirm-or-retire cycle |
  | CDC content (milestone checklists substantively revised 2022; ADDM ~2-year cycle) | Semi-annually, and on ADDM release |
  | CPIR / parent-centre material | Quarterly |
  | PMC OA literature | Incremental weekly/monthly, **retraction watch mandatory** |
  | NCAEP/AFIRM EBP list (~6-year review cycle) | Annually |

- **Withdrawal detection is a first-class requirement**, not a side effect of re-crawling:
  federal guidance is rescinded as well as issued, and a rescinded document often stays
  reachable at its old URL.
- **Retraction watch** for the literature tier, using the retraction and correction signals
  available through the PMC APIs.
- A freshness report: what was re-checked, what changed, what was tombstoned, what failed to
  fetch. A source that silently stops updating is itself a defect.

## Implementation notes
- Tombstones are records, not deletions. The chunk stays, its status changes, and the reason
  and date are recorded — otherwise "why did it stop saying that?" is unanswerable.
- Supersession is a graph, not a flag: guidance is often replaced by a differently-titled
  document at a different URL, so the link must be recorded explicitly when detected.
- Respect NCBI rate limits (≤3 requests/sec, bulk off-peak) in the incremental job.
- Run it as a scheduled job with a written report, not a cron that fails quietly.
- OpenSpec docstrings; explicit errors, no bare `except`.

## Tests (fixtures only)
- A tombstoned chunk is never returned as `current`.
- A chunk marked `superseded_by` resolves to its successor, and the successor exists.
- A retracted-article fixture is caught by the retraction pass and status-changed.
- A withdrawn-guidance fixture still reachable at its URL is detected and tombstoned.
- A source that fails to fetch for N cycles is surfaced in the report, not silently skipped.
