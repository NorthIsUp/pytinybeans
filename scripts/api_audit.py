"""Probe Tinybeans API surface and diff against pytinybeans models.

Hits each endpoint with raw HTTP, dumps the full response JSON to
/tmp/tb-audit/, then compares observed top-level keys against what each
pydantic model declares — so we can see what TB sends that we currently
discard (extra="allow") and what we declare but TB no longer sends.

Usage:
    TINYBEANS_LOGIN=... TINYBEANS_PASSWORD=... python scripts/api_audit.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import aiohttp

from pytinybeans.pytinybeans import (
    IOS_CLIENT_ID,
    TinybeanChild,
    TinybeanComment,
    TinybeanEntry,
    TinybeanFollowing,
    TinybeanJournal,
    TinybeansUser,
    TinybeanBlobs,
)

BASE = "https://tinybeans.com/api/1/"
OUT = Path("/tmp/tb-audit")
OUT.mkdir(exist_ok=True)


async def post(session, path, body):
    async with session.post(f"{BASE}{path}", json=body) as r:
        r.raise_for_status()
        return await r.json()


async def get(session, path, params=None):
    async with session.get(f"{BASE}{path}", params=params or {}) as r:
        r.raise_for_status()
        return await r.json()


def model_field_names(model_cls) -> set[str]:
    return {f.alias or n for n, f in model_cls.model_fields.items()}


def compare(label: str, observed: dict, model_cls) -> None:
    declared = model_field_names(model_cls)
    obs = set(observed.keys())
    extra = sorted(obs - declared)
    missing = sorted(declared - obs)
    print(f"\n=== {label} vs {model_cls.__name__} ===")
    print(f"  observed keys: {len(obs)}, model fields: {len(declared)}")
    if extra:
        print(f"  EXTRA on wire (we discard): {extra}")
    if missing:
        print(f"  declared but not in response: {missing}")
    if not extra and not missing:
        print("  ✓ perfect match")


async def main() -> None:
    user = os.environ["TINYBEANS_LOGIN"]
    pw = os.environ["TINYBEANS_PASSWORD"]

    async with aiohttp.ClientSession() as session:
        # 1. authenticate
        auth = await post(session, "authenticate", {
            "username": user, "password": pw, "clientId": IOS_CLIENT_ID,
        })
        token = auth["accessToken"]
        (OUT / "authenticate.json").write_text(json.dumps(auth, indent=2, default=str))
        print(f"authenticated as {auth['user'].get('emailAddress')}, token={token[:20]}…")
        compare("authenticate.user", auth["user"], TinybeansUser)

        session.headers.update({"authorization": token})

        # 2. me (if it exists)
        for path in ["me", "users/me", "users/current"]:
            try:
                me = await get(session, path)
                (OUT / "me.json").write_text(json.dumps(me, indent=2, default=str))
                print(f"\n--- /{path} top-level keys: {sorted(me.keys())}")
                break
            except aiohttp.ClientResponseError as e:
                print(f"  /{path}: {e.status}")

        # 3. followings
        fol = await get(session, "followings", {"clientId": IOS_CLIENT_ID})
        (OUT / "followings.json").write_text(json.dumps(fol, indent=2, default=str))
        print(f"\nfollowings envelope keys: {sorted(fol.keys())}")
        if fol["followings"]:
            f = fol["followings"][0]
            compare("followings[0]", f, TinybeanFollowing)
            compare("followings[0].journal", f["journal"], TinybeanJournal)
            if f["journal"]["children"]:
                compare("followings[0].journal.children[0]", f["journal"]["children"][0], TinybeanChild)

        # 4. entries — first page of first journal w/ children
        target_journal = None
        for f in fol["followings"]:
            if f["journal"].get("children"):
                target_journal = f["journal"]["id"]
                break
        if not target_journal:
            print("no journal with children; skipping entries probe")
            return
        ent = await get(session, f"journals/{target_journal}/entries", {
            "clientId": IOS_CLIENT_ID, "fetchSize": 50,
        })
        (OUT / "entries.json").write_text(json.dumps(ent, indent=2, default=str))
        print(f"\nentries envelope keys: {sorted(ent.keys())}  (numEntriesRemaining={ent.get('numEntriesRemaining')})")
        if ent["entries"]:
            compare("entries[0]", ent["entries"][0], TinybeanEntry)
            compare("entries[0].blobs", ent["entries"][0].get("blobs", {}), TinybeanBlobs)
            if ent["entries"][0].get("comments"):
                compare("entries[0].comments[0]", ent["entries"][0]["comments"][0], TinybeanComment)

        # 5. milestones (undocumented endpoint, might exist)
        for path in [f"journals/{target_journal}/milestones", f"children/{fol['followings'][0]['journal']['children'][0]['id']}/milestones"]:
            try:
                ms = await get(session, path, {"clientId": IOS_CLIENT_ID})
                (OUT / f"milestones-{path.replace('/', '_')}.json").write_text(json.dumps(ms, indent=2, default=str))
                print(f"\n  /{path}: keys={sorted(ms.keys())}")
                if ms.get("milestones"):
                    print(f"    milestones[0] keys: {sorted(ms['milestones'][0].keys())}")
                break
            except aiohttp.ClientResponseError as e:
                print(f"  /{path}: {e.status}")

        # 6. emotions / reactions — try to find them
        for ent0 in ent["entries"][:3]:
            for path in [f"entries/{ent0['id']}/emotions", f"entries/{ent0['id']}/reactions"]:
                try:
                    em = await get(session, path, {"clientId": IOS_CLIENT_ID})
                    (OUT / f"emotions-{ent0['id']}.json").write_text(json.dumps(em, indent=2, default=str))
                    print(f"\n  /{path}: keys={sorted(em.keys()) if isinstance(em, dict) else 'list'}")
                except aiohttp.ClientResponseError as e:
                    print(f"  /{path}: {e.status}")

        # 7. comments endpoint?
        for ent0 in ent["entries"][:3]:
            if not ent0.get("comments"):
                continue
            try:
                cm = await get(session, f"entries/{ent0['id']}/comments", {"clientId": IOS_CLIENT_ID})
                (OUT / f"comments-{ent0['id']}.json").write_text(json.dumps(cm, indent=2, default=str))
                print(f"  /entries/{ent0['id']}/comments: {sorted(cm.keys()) if isinstance(cm, dict) else 'list'}")
                break
            except aiohttp.ClientResponseError as e:
                print(f"  comments: {e.status}")
                break

        print(f"\nAll responses dumped to {OUT}/")


if __name__ == "__main__":
    asyncio.run(main())
