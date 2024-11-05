from abc import ABC
from copy import deepcopy

from fastapi import APIRouter
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from losdos.mixins.create import CreateMixin
from losdos.mixins.delete import DeleteMixin
from losdos.mixins.patch import PatchMixin
from losdos.mixins.read import ReadMixin
from losdos.mixins.search import SearchMixin


class RouterParams(ABC):
    prefix = None
    tags = None
    dependencies = None


class Base(DeclarativeBase):
    pass


class ResourceBase:
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(unique=True)

    class router_cfg(RouterParams):
        pass


class Resource(
    ResourceBase, CreateMixin, ReadMixin, PatchMixin, DeleteMixin, SearchMixin
):

    def nullraise(self):
        raise ValueError("No sessionmaker attached to Resource class")

    _sessionmaker = nullraise

    @classmethod
    def build_router(cls) -> None:

        cls.router = APIRouter(
            prefix=cls.router_cfg.prefix or f"/{cls.__name__.lower()}",
            tags=cls.router_cfg.tags,
            dependencies=cls.router_cfg.dependencies,
        )

        if hasattr(cls, "build_create"):
            cls.build_create()
        if hasattr(cls, "build_read"):
            cls.build_read()
        if hasattr(cls, "build_update"):
            cls.build_update()
        if hasattr(cls, "build_delete"):
            cls.build_delete()
        if hasattr(cls, "build_search"):
            cls.build_search()

    @classmethod
    def db_generator(cls) -> Session:
        try:
            db = cls._sessionmaker()
            yield db
        finally:
            if db is not None:
                db.close()

    @classmethod
    def with_sessionmaker(cls, session_maker: callable) -> "Resource":

        new_cls = deepcopy(cls)
        new_cls._sessionmaker = session_maker
        return new_cls
