from __future__ import annotations

from asyncio import sleep
from datetime import date, datetime
from functools import cached_property, partial
from itertools import count
from typing import (Any, AsyncGenerator, Dict, Iterable, List, Optional,
                    Sequence, Union)
from urllib.parse import urljoin

import aiohttp
import inflection
from pydantic import BaseModel, Field, typing, validator

IOS_CLIENT_ID = '13bcd503-2137-9085-a437-d9f2ac9281a1'


class BaseTinybean(BaseModel):
    class Config:
        alias_generator = partial(inflection.camelize, uppercase_first_letter=False)
        extra = 'allow'

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self.__post_init__()

    def __post_init__(self) -> None:
        pass

    def __repr_args__(self) -> typing.ReprArgs:
        return [
            (k, v)
            for k, v in self.__dict__.items()
            if ((f := self.__fields__.get(k)) and f.field_info.extra.get('repr') == True)
        ]

    def __str__(self) -> str:
        return repr(self)


class TinybeansUser(BaseTinybean):
    id: int = Field(repr=True)
    first_name: str
    last_name: str
    email_address: str
    username: str = Field(repr=True)


class TinybeanRelationshiop(BaseTinybean):
    label: str = Field(repr=True)
    name: str = Field(repr=True)  # father/friend/etc.

    @property
    def is_parent(self) -> bool:
        return self.label.lower() in ('father', 'mother')


class TinybeanChild(BaseTinybean):
    id: int = Field(repr=True)
    first_name: str = Field(repr=True)
    last_name: str
    gender: str
    dob: date = Field(repr=True)
    _journal: Optional[TinybeanJournal] = None
    # journal: TinybeanJournal

    @validator('dob', pre=True)
    def parse_dob(cls, v: str):
        return datetime.strptime(v, '%Y-%m-%d').date()

    @property
    def name(self):
        return f'{self.first_name} {self.last_name}'

    @property
    def journal(self) -> TinybeanJournal:
        assert self._journal is not None, 'journal must be set'
        return self._journal


class TinybeanJournal(BaseTinybean):
    id: int = Field(repr=True)
    title: str = Field(repr=True)
    children: List[TinybeanChild]

    def __post_init__(self):
        for child in self.children:
            print(f'setting journal on child {child}')
            child._journal = self  # type: ignore


class TinybeanFollowing(BaseTinybean):
    id: int = Field(repr=True)
    url: str = Field(alias='URL')
    relationship: TinybeanRelationshiop
    journal: TinybeanJournal


class TinybeanComment(BaseTinybean):
    id: int = Field(repr=True)
    details: str = Field(repr=True)
    user: TinybeansUser


class TinybeanEmotion(BaseTinybean):
    id: int
    entry_id: int
    user_id: int
    type: Dict[str, Any]


class TinybeanBlobs(BaseTinybean):
    o: str = Field(repr=True)

    @property
    def best(self) -> str:
        for k in ('o', 'o2', 't', 's', 's2', 'm', 'l', 'p'):
            if v := getattr(self, k, None):
                return v
        raise ValueError(f'No best blob found for {self}')


class TinybeanEntry(BaseTinybean):
    id: int = Field(repr=True)
    uuid: str = Field(repr=True)
    timestamp: datetime
    type: str = Field(repr=True)
    caption: str = Field(repr=True)
    blobs: TinybeanBlobs
    attachment_type: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    attachment_url__mp4: Optional[str] = None
    emotions: List[TinybeanEmotion] = Field(default_factory=list)
    comments: List[TinybeanComment] = Field(default_factory=list)

    @validator('timestamp', pre=True)
    def validate_timestamp(cls, value: str) -> datetime:
        return datetime.fromtimestamp(float(value) / 1000)

    @validator('attachment_type', pre=True)
    def validate_attachment_type(
        cls, v: str, values: Sequence[str], **kwargs: Any
    ) -> Optional[str]:
        if v == 'VIDEO':
            return v
        else:
            return kwargs.get('type')

    @property
    def is_video(self) -> bool:
        return self.attachment_type == 'VIDEO'

    @property
    def is_photo(self) -> bool:
        return self.type == 'PHOTO' and not self.is_video

    @property
    def is_text(self) -> bool:
        return self.type == 'TEXT'

    @property
    def url(self) -> str:
        if self.is_video:
            return self.video_url
        elif self.is_photo:
            return self.photo_url
        raise ValueError(f'No url for type {self.type}')

    @property
    def photo_url(self) -> str:
        if self.is_photo:
            return self.blobs.best
        raise ValueError(f'No photo url for {self.type}')

    @property
    def video_url(self) -> str:
        if self.is_video and self.attachment_url__mp4:
            return self.attachment_url__mp4
        raise ValueError(f'No video url for {self.type}')


class PyTinybeans:
    API_BASE_URL = 'https://tinybeans.com/api/1/'
    CLIENT_ID = IOS_CLIENT_ID

    def __init__(self) -> None:
        self.session = aiohttp.ClientSession()
        self._access_token = None

    async def _api(
        self,
        path: str,
        params: Optional[Dict[str, Union[None, str, int]]] = None,
        json: Optional[Dict[str, str]] = None,
        method: str = 'GET',
    ) -> aiohttp.ClientResponse:
        url = urljoin(self.API_BASE_URL, path)

        if self._access_token:
            response = await self.session.request(
                method,
                url,
                params=params,
                json=json,
                headers={'authorization': self._access_token},
            )
        else:
            response = await self.session.request(
                method,
                url,
                params=params,
                json=json,
            )

        # print(response.text)
        return response

    @property
    def logged_in(self):
        if self._access_token:
            return True

        return False

    async def login(self, username: str, password: str) -> bool:
        if self.logged_in:
            # check via api/me or something that this token works
            return self.logged_in

        response = await self._api(
            path='authenticate',
            json={
                'username': username,
                'password': password,
                'clientId': IOS_CLIENT_ID,
            },
            method='POST',
        )

        response.raise_for_status()
        response_json = await response.json()

        self._access_token = response_json['accessToken']
        self.user = TinybeansUser(**response_json['user'])

        return self.logged_in

    async def get_followings(self) -> AsyncGenerator[TinybeanFollowing]:
        response = await self._api(
            path='followings',
            params={'clientId': self.CLIENT_ID},
        )

        response.raise_for_status()

        response_json = await response.json()

        for following in response_json['followings']:
            yield TinybeanFollowing(**following)

    @property
    async def children(self) -> List[TinybeanChild]:
        children: List[TinybeanChild] = []
        async for following in self.get_followings():
            children.extend(following.journal.children)

        return children

    async def get_entries(
        self,
        child: TinybeanChild,
        last: Optional[int] = None,
        limit: Union[None, int, datetime] = None,
    ) -> List[TinybeanEntry]:
        if last is None:
            last = int(datetime.utcnow().timestamp() * 1000)

        _counter: Optional[Iterable[int]] = count() if isinstance(limit, int) else None

        def limit_check(entry: TinybeanEntry) -> bool:
            # return True if limit is reached
            if _counter:
                return limit <= next(_counter)
            elif isinstance(limit, datetime):
                return limit > entry.timestamp
            return False

        response_json: Dict[str, Any] = {'numEntriesRemaining': 1}
        while response_json.get('numEntriesRemaining', 0) > 0:
            response = await self._api(
                path=f'journals/{child.journal.id}/entries',
                params={
                    'clientId': self.CLIENT_ID,
                    'fetchSize': 200,
                    'last': last,
                },
            )
            response.raise_for_status()
            response_json = await response.json()

            for entry_json in response_json['entries']:
                entry = TinybeanEntry(**entry_json)
                if limit_check(entry):
                    return
                yield entry

            last = entry.timestamp

    async def request_export(
        self, journal: TinybeanJournal, start_dt: datetime, end_dt: datetime
    ) -> bool:
        response = self._api(
            method='POST',
            path='/api/1/journals/{journal_id}/export'.format(journal_id=journal.id),
            params={
                'startDate': start_dt.strftime('%Y-%m-%d'),
                'endDate': end_dt.strftime('%Y-%m-%d'),
            },
        )

        response.raise_for_status()
        response_json = await response.json()
        if response_json['status'] == 'ok':
            return True

        return False
