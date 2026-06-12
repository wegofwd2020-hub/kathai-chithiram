# KC-1 — Verifiable hard-delete of story, scene script, and media

**Labels:** P0, privacy, compliance
**Refs:** PRIVACY.md §5

## Why
Parents must be able to delete a story and have *all* derived artifacts removed; this is the highest-risk privacy obligation.

## Acceptance criteria
- A `delete_story(story_id)` operation hard-deletes raw story text, the derived scene script, and rendered media (and caches).
- Deletion cascades to backups on the next backup cycle (documented).
- No tombstoned copies of raw story text remain.
- Default retention job deletes undelivered story text after 30 days.

## Implementation notes
- Add a deletion service with OpenSpec docstring; raise `StoryNotFoundError` / `DeletionError` explicitly.
- Test with mock stories asserting every artifact path is gone post-delete.
