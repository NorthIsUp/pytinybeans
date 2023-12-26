from os import environ

import pytest
from dotenv import load_dotenv

import pytinybeans
from pytinybeans.pytinybeans import PyTinybeans, TinybeanJournal


@pytest.fixture
def env_prefix() -> str:
    load_dotenv()
    return environ.get("ENV_PREFIX", "")


@pytest.fixture
def child_id():
    return 887863


@pytest.fixture
async def api(env_prefix):
    api = pytinybeans.PyTinybeans()
    username = environ[f"{env_prefix}TINYBEANS_LOGIN"]
    password = environ[f"{env_prefix}TINYBEANS_PASSWORD"]
    await api.login(username=username, password=password)
    return api


@pytest.fixture()
async def my_journal(api: PyTinybeans) -> TinybeanJournal:
    async for following in api.get_followings():
        if following.relationship.is_parent:
            return following.journal


def test_api(api: PyTinybeans, my_journal: TinybeanJournal):
    child = my_journal.children[0]
    assert child.journal
    entries = list(api.get_entries(child, limit=3))
    assert len(entries) == 3
