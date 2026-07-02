from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict


@dataclass
class Page:
    id: str
    title: str
    url: str
    text: str

    def to_dict(self):
        return asdict(self)


@dataclass
class Thread:
    id: str
    type: str
    author: str
    created_at: str
    updated_at: str
    comment_text: str
    permalink: str
    anchor: str | None

    def to_dict(self):
        return asdict(self)


class DocSource(ABC):
    @abstractmethod
    def resolve(self, ref: str) -> Page: ...

    @abstractmethod
    def list_threads(self, page: Page) -> list: ...

    @abstractmethod
    def post_reply(self, thread: Thread, text: str) -> None: ...
