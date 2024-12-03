from abc import ABC
from copy import deepcopy
from typing import ForwardRef

from fastapi import APIRouter
from pydantic import create_model
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from quickrest.mixins.create import CreateMixin
from quickrest.mixins.patch import PatchMixin
from quickrest.mixins.read import ReadMixin


class RouterParams(ABC):
    prefix = None
    tags = None
    dependencies = None


class ResourceParams(ABC):
    children: list[str] = []
    serialize: list[str] = []


class Base(DeclarativeBase):
    pass


class ResourceBase:
    id: Mapped[str] = mapped_column(primary_key=True)

    class router_cfg(RouterParams):
        pass

    class resource_cfg(ResourceParams):
        pass


class Resource(
    ResourceBase,
    CreateMixin,
    ReadMixin,
    PatchMixin,
    # DeleteMixin,
    # SearchMixin,
):

    def nullraise(self):
        raise ValueError("No sessionmaker attached to Resource class")

    _sessionmaker = nullraise

    @classmethod
    def _build_basemodel(cls):
        cols = [c for c in cls.__table__.columns]

        fields = {c.name: (c.type.python_type, ...) for c in cols}

        for r in cls.__mapper__.relationships:
            if r.key in cls.resource_cfg.serialize:
                fields[r.key] = (ForwardRef(r.mapper.class_.__name__), ...)

        return create_model(cls.__name__, **fields)

    @classmethod
    def build_models(cls):

        cls.basemodel = cls._build_basemodel()

        for attr in ["read", "create"]:
            if hasattr(cls, attr):
                getattr(cls, attr)

    @classmethod
    def build_router(cls) -> None:

        cls.router = APIRouter(
            prefix=cls.router_cfg.prefix or f"/{cls.__tablename__}",
            tags=cls.router_cfg.tags,
            dependencies=cls.router_cfg.dependencies,
        )

        if hasattr(cls, "read"):
            cls.read.attach_route(cls)
        if hasattr(cls, "create"):
            cls.create.attach_route(cls)
        # if hasattr(cls, "update"):
        #     cls.update.attach_route(cls)
        # if hasattr(cls, "build_delete"):
        #     cls.build_delete()
        # if hasattr(cls, "build_search"):
        #     cls.build_search()

        return cls.router

    @classmethod
    def db_generator(cls) -> Session:
        try:
            db = cls._sessionmaker()
            yield db
        finally:
            if db is not None:
                db.close()

    @classmethod
    def from_factory(cls, sessionmaker: callable) -> "Resource":

        new_cls = deepcopy(cls)
        new_cls._sessionmaker = sessionmaker
        return new_cls
