from os import environ

import pytest
import pytinybeans
from pytinybeans.pytinybeans import PyTinybeans, TinybeanJournal


@pytest.fixture
def child_id():
    return 887863


@pytest.fixture
def api():
    api = pytinybeans.PyTinybeans()
    username = environ['NORTHISBOT__TINYBEANS__LOGIN']
    password = environ['NORTHISBOT__TINYBEANS__PASSWORD']
    api.login(username=username, password=password)
    return api


@pytest.fixture()
def my_journal(api: PyTinybeans) -> TinybeanJournal:
    return next(f for f in api.get_followings() if f.relationship.is_parent).journal


def test_api(api: PyTinybeans, my_journal: TinybeanJournal):
    child = my_journal.children[0]
    assert child.journal
    entries = list(api.get_entries(child, limit=3))
    assert len(entries) == 3
