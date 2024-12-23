from abc import ABC
from typing import ForwardRef, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter
from pydantic import BaseModel, create_model
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.types import Uuid

from quickrest.mixins.create import CreateMixin
from quickrest.mixins.delete import DeleteMixin
from quickrest.mixins.errors import default_error_handler
from quickrest.mixins.patch import PatchMixin
from quickrest.mixins.read import ReadMixin
from quickrest.mixins.search import SearchMixin


def nullraise(caller):
    raise ValueError(f"{caller.__name__} - No callable declared")


def nullreturn():
    return None


class RouterParams(ABC):
    prefix = None
    tags = None
    dependencies = None


class ResourceParams(ABC):
    routed_relationships: list[str] = []
    serialize: list[str] = []


class Base(DeclarativeBase):
    pass


class ResourceBaseStr:
    id: Mapped[str] = mapped_column(primary_key=True)


class ResourceBaseUUID:
    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )


class ResourceBaseInt:
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)


class ResourceBaseSlug:
    slug: Mapped[str] = mapped_column(unique=True)
    primary_key = "slug"


class ResourceBaseSlugPass:
    primary_key = "id"


class ResourceMixin:

    class router_cfg(RouterParams):
        pass

    class resource_cfg(ResourceParams):
        pass

    @classmethod
    def _build_basemodel(cls):
        cols = [c for c in cls.__table__.columns]

        fields = {
            c.name: (
                (Optional[c.type.python_type], None)
                if c.nullable
                else (c.type.python_type, ...)
            )
            for c in cols
        }

        for r in cls.__mapper__.relationships:
            if r.key in cls.resource_cfg.serialize:

                if len(r.remote_side) > 1:
                    # if the relationship is many-to-many, we need to use a list
                    fields[r.key] = (list[ForwardRef(r.mapper.class_.__name__)], ...)
                else:
                    # otherwise, we can just use the type of the primary key
                    fields[r.key] = (ForwardRef(r.mapper.class_.__name__), ...)

        return create_model(cls.__name__, **fields)

    @classmethod
    def build_models(cls):

        cls.basemodel = cls._build_basemodel()

        for attr in ["read", "create", "delete"]:
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
        if hasattr(cls, "delete"):
            cls.delete.attach_route(cls)
        if hasattr(cls, "patch"):
            cls.patch.attach_route(cls)
        if hasattr(cls, "search"):
            print("YEAr SEARCH")
            cls.search.attach_route(cls)

        return cls.router

    @classmethod
    async def db_generator(cls) -> Session:
        try:
            db = cls._sessionmaker()
            yield db
        finally:
            if db is not None:
                db.close()


def build_resource(
    sessionmaker: callable = nullraise,
    user_generator: callable = nullreturn,
    user_token_model: BaseModel = None,
    id_type: type = str,
    slug: bool = False,
    error_handler: callable = default_error_handler,
) -> type:

    if id_type is str:
        ResourceBase = ResourceBaseStr
    elif id_type is UUID:
        ResourceBase = ResourceBaseUUID
    elif id_type is int:
        ResourceBase = ResourceBaseInt
    else:
        raise ValueError(f"id_type must be str, uuid.UUID, or int, got {id_type}")

    class Resource(
        ResourceBase,
        ResourceBaseSlug if slug else ResourceBaseSlugPass,
        ResourceMixin,
        CreateMixin,
        ReadMixin,
        PatchMixin,
        DeleteMixin,
        SearchMixin,
    ):
        _id_type = id_type
        _sessionmaker = sessionmaker
        _user_generator = user_generator
        _user_token = user_token_model
        _error_handler = error_handler

    return Resource
