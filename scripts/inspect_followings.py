"""Print every following with its ownership flags, so we can pick the right filter."""

from __future__ import annotations

import asyncio
import os
import sys

from pytinybeans.pytinybeans import PyTinybeans


async def main() -> None:
    tb = PyTinybeans()
    await tb.login(os.environ["TINYBEANS_LOGIN"], os.environ["TINYBEANS_PASSWORD"])
    async for f in tb.get_followings():
        kids = [c.first_name for c in f.journal.children]
        rel = f.relationship.label if f.relationship else None
        print(
            f"journal={f.journal.title!r:30} "
            f"kids={kids} "
            f"rel={rel!s:15} "
            f"co_owner={f.co_owner} "
            f"add_entries={f.add_entries} "
            f"view_entries={f.view_entries}",
            file=sys.stdout,
        )


if __name__ == "__main__":
    asyncio.run(main())
