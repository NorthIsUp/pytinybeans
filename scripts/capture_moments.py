"""Dump the raw entries payload so we can see how multi-photo moments are shaped.

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

from pytinybeans.pytinybeans import PyTinybeans


async def main() -> None:
    tb = PyTinybeans()
    await tb.login(os.environ["TINYBEANS_LOGIN"], os.environ["TINYBEANS_PASSWORD"])

    children = await tb.children
    if not children:
        raise SystemExit("no children on this account")
    child = children[0]

    # Hit the raw endpoint so we see fields the model currently discards.
    resp = await tb._api(  # noqa: SLF001
        path=f"journals/{child.journal.id}/entries",
        params={"clientId": tb.CLIENT_ID, "fetchSize": 50},
    )
    data = await resp.json()
    print(json.dumps(data, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
