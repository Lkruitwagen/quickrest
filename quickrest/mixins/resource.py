from abc import ABC
from typing import ForwardRef

from fastapi import APIRouter
from pydantic import BaseModel, create_model
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from quickrest.mixins.create import CreateMixin
from quickrest.mixins.errors import default_error_handler
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


class _Resource(
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
    _user_generator = nullraise
    _user_token = None
    _error_handler = default_error_handler

    @classmethod
    def _build_basemodel(cls):
        cols = [c for c in cls.__table__.columns]

        fields = {c.name: (c.type.python_type, ...) for c in cols}

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

    # @classmethod
    # def from_factory(cls, sessionmaker: callable) -> "Resource":

    #     new_cls = deepcopy(cls)
    #     new_cls._sessionmaker = sessionmaker
    #     return new_cls


def build_resource(
    sessionmaker: callable,
    user_generator: callable,
    user_token_model: BaseModel,
    error_handler: callable = default_error_handler,
) -> type:

    class Resource(_Resource):
        _sessionmaker = sessionmaker
        _user_generator = user_generator
        _user_token = user_token_model
        _error_handler = error_handler

    return Resource
