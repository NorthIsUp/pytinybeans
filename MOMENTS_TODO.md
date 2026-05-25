# Multi-photo "moments" — investigation notes

Context: `TinybeanEntry` currently exposes a single `blobs: TinybeanBlobs`
plus one optional `attachment_url__mp4`. In the Tinybeans mobile/web UI a
single "moment" (one day, one caption, one set of reactions/comments) can
hold multiple photos and/or a video. We need to figure out how the API
represents that so the archiver (tinyframe) can rebuild moments faithfully
across years of history.

## What's already in this repo

- `TinybeanEntry` fields seen in code: `id`, `uuid`, `timestamp`, `type`,
  `caption`, `blobs`, `attachment_type`, `latitude`, `longitude`,
  `attachment_url__mp4`, `emotions`, `comments`. `BaseTinybean` is
  configured with `extra="allow"`, so the server is presumably sending
  more fields that we're silently discarding.
- The `entries` endpoint returns `{"entries": [...], "numEntriesRemaining": N}`.
  No `groups`/`moments`/`days` envelope is referenced anywhere.
- Each entry already has both `id` (int) and `uuid` (string). The presence
  of *both* is suspicious: typically a moment would have a stable uuid
  shared across its child photo entries while each photo gets its own
  numeric id. Worth verifying.
- There's no `parent_id`, `group_id`, `moment_id`, `siblings`, or
  `attachments` list referenced anywhere — so if the API exposes one,
  it's currently being swallowed by `extra="allow"`.

## Hypotheses to confirm with a live capture

Run one `get_entries(...)` call against a known multi-photo day and dump
the raw JSON for ~50 entries. Look for any of these patterns:

1. **Flat siblings.** Each photo is its own entry; they share a field
   like `groupUUID` / `momentId` / `dayUuid`. Caption is duplicated on
   each. Reactions/comments may be duplicated too, or only attached to
   the "primary" entry.
   - If true: model gains `group_uuid: Optional[str]`, and we add a
     helper on `PyTinybeans` to fold entries into moments client-side.

2. **Nested attachments.** A single entry has an `attachments: [...]` or
   `blobs: [...]` (list) field, each with its own `o/o2/...` URLs. The
   top-level `blobs` we see today is just the first/primary.
   - If true: `TinybeanEntry.blobs` becomes `List[TinybeanBlobs]` (or we
     keep `blobs` as primary and add `attachments: List[TinybeanBlobs]`
     for back-compat). `is_video`/`is_photo` need to operate per-attachment.

3. **Mixed.** A "carousel" entry has type like `MULTI` / `GROUP` and
   carries an `entries: [...]` or `items: [...]` subarray.
   - If true: introduce `TinybeanMoment` wrapping a list of
     `TinybeanEntry` and have `get_entries` yield moments by default,
     with a `get_raw_entries` escape hatch.

## Concrete capture script the user should run

```python
import json, asyncio, os
from pytinybeans import PyTinybeans

async def main():
    tb = PyTinybeans()
    await tb.login(os.environ["TINYBEANS_LOGIN"], os.environ["TINYBEANS_PASSWORD"])
    child = (await tb.children)[0]
    # bypass the model so we see the raw shape
    resp = await tb._api(
        path=f"journals/{child.journal.id}/entries",
        params={"clientId": tb.CLIENT_ID, "fetchSize": 50},
    )
    data = await resp.json()
    print(json.dumps(data, indent=2, default=str))

asyncio.run(main())
```

Pipe to a file, grep for keys we don't model yet:

```sh
python capture.py > entries.json
python -c "import json; d=json.load(open('entries.json')); \
  print(sorted({k for e in d['entries'] for k in e}))"
```

That key list will tell us immediately which hypothesis is right.

## Proposed model change (DO NOT SHIP YET)

Pending the capture, the least invasive shape is:

```python
class TinybeanAttachment(BaseTinybean):
    blobs: TinybeanBlobs
    attachment_type: Optional[str] = None       # "VIDEO" or None
    attachment_url__mp4: Optional[str] = None

class TinybeanEntry(BaseTinybean):
    id: int
    uuid: str
    group_uuid: Optional[str] = None            # NEW — shared across siblings
    timestamp: datetime
    type: str
    caption: str
    # Back-compat: keep `blobs` as the primary attachment's blobs.
    blobs: TinybeanBlobs
    attachments: List[TinybeanAttachment] = Field(default_factory=list)
    ...
```

Plus a `PyTinybeans.get_moments(child, ...)` async generator that groups
consecutive entries by `group_uuid` (falling back to `uuid` so single-photo
moments still work).

If hypothesis #2 (nested attachments inside one entry) wins instead, we
skip `group_uuid` and just populate `attachments` from the nested list —
the public surface is the same.

## Open questions for the user

- Does Tinybeans surface "moments" in the API or only in the UI?
- For multi-photo days, are reactions/comments per-photo or per-moment?
- Do videos and photos ever live inside the same moment?
- Is `uuid` per-entry or per-moment? (The presence of both `id` and `uuid`
  on the same entry strongly suggests one of them is the grouping key.)
