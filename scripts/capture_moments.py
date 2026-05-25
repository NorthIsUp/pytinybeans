"""Dump the raw entries payload so we can see how multi-photo moments are shaped.

Bypasses the `tb.children` accessor because TinybeanFollowing requires a
`relationship` field that isn't always present in the API response.

Usage:
    TINYBEANS_LOGIN=... TINYBEANS_PASSWORD=... python scripts/capture_moments.py > entries.json

Then look at the keys we don't model yet:
    python -c "import json; d=json.load(open('entries.json')); \
      print(sorted({k for e in d['entries'] for k in e}))"
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

from pytinybeans.pytinybeans import PyTinybeans


async def main() -> None:
    tb = PyTinybeans()
    await tb.login(os.environ["TINYBEANS_LOGIN"], os.environ["TINYBEANS_PASSWORD"])

    followings_resp = await tb._api(path="followings")  # noqa: SLF001
    followings = (await followings_resp.json())["followings"]
    print(
        "FOLLOWINGS top-level keys:",
        sorted({k for f in followings for k in f}),
        file=sys.stderr,
    )

    journal_id = None
    for f in followings:
        j = f.get("journal", {})
        if j.get("children"):
            journal_id = j["id"]
            print(
                f"using journal {journal_id} (title={j.get('title')!r}, "
                f"children={[c['firstName'] for c in j['children']]})",
                file=sys.stderr,
            )
            break
    if not journal_id:
        raise SystemExit("no journal with children found")

    entries_resp = await tb._api(  # noqa: SLF001
        path=f"journals/{journal_id}/entries",
        params={"clientId": tb.CLIENT_ID, "fetchSize": 100},
    )
    payload = await entries_resp.json()
    json.dump(payload, sys.stdout, indent=2, default=str)


if __name__ == "__main__":
    asyncio.run(main())
