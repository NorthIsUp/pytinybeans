# Multi-photo "moments" — investigation complete

**Conclusion: there are no multi-photo moments to model.** Each Tinybeans
entry is exactly one photo or one video. Multiple uploads on the same day
are independent entries with their own captions, `clientRef`s, and
`sortOrder` values (1, 2, 3, ...). There is no `groupUUID`, no
`attachments` list, no `MULTI`/`GROUP` type.

## Evidence (capture from a real journal, 100 entries)

- All 100 entries have unique `uuid`s.
- No `groupUUID`, `momentId`, `parentId`, `parentUUID`, `dayUuid`,
  `siblings`, or `attachments` fields.
- Each entry has exactly one `blobs` dict (one image, with size variants
  `o`/`o2`/`l`/`m`/`s`/`s2`/`t`/`p`).
- 22/72 days had multiple entries; each entry on those days carries a
  distinct caption and a distinct `clientRef` (iOS app's local UUID).
  `sortOrder` increments per-day.
- `type` is always `PHOTO` even when `attachmentType="VIDEO"` — type is
  not a discriminator for grouping.

## Action

The existing single-blob `TinybeanEntry` model is correct. Archivers will
get one row per photo, which is the right shape.

## Other findings worth acting on

- `deleted: bool` is exposed on every entry. Filter `deleted=True` out at
  the sync layer.
- `orientation: "LANDSCAPE" | "PORTRAIT"` is provided per entry. Worth
  exposing on `TinybeanEntry` so downstream frames can use it.
- `children` is a list on each entry — usually len 1, but the schema
  allows multiple. Currently swallowed by `extra="allow"`.
- `TinybeanFollowing.relationship` was required but is sometimes missing
  on the wire — made `Optional` in a follow-up commit.
- Videos populate `attachmentUrl`, `attachmentUrl_mp4`, `attachmentUrl_webm`
  AND `blobs` (poster frames). Currently we use `attachmentUrl_mp4`.

These are minor; capture from a wider time range if any look wrong.
