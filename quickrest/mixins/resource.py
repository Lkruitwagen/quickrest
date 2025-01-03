from abc import ABC
from enum import Enum
from typing import Callable, ForwardRef, Generator, Optional, Type
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, create_model
from sqlalchemy import create_engine
from sqlalchemy.ext.associationproxy import ColumnAssociationProxyInstance
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.types import Uuid

from quickrest.mixins.base import env_settings
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


def default_sessionmaker():
    if env_settings.DB_PATH:
        engine = create_engine(env_settings.DB_PATH, echo=False)
        return sessionmaker(bind=engine)
    else:
        return nullraise


class RouterParams(ABC):
    """
    The RouterParams class is an abstract class that defines the parameters for the APIRouter.
    It can be used to set router-level parameters that affect all routes in the router.
    Individual routes (`read_cfg`, `create_cfg`, etc.) can override there parameters.

    Attributes:
        prefix (Optional[str]): The prefix for the APIRouter.
        tags (Optional[list[str]]): A list of tags for the APIRouter.
        dependencies (list[Callable]): Injectible dependencies for the APIRouter.

    ## Example

    ```python
    from sqlalchemy.orm import Mapped, mapped_column

    from quickrest import Base, Resource

    from some_package.auth import must_be_admin


    class Student(Base, Resource):
        __tablename__ = "companies"

        first_name: Mapped[str] = mapped_column()
        last_name: Mapped[str] = mapped_column()

        class route_cfg(RouterParams):
            prefix = "api"
            tags = ["students"]
            dependencies = [must_be_admin]
    ```

    """

    prefix: Optional[str] = None
    tags: Optional[list[str | Enum]] = None
    dependencies: list[Callable] = []


class ResourceParams(ABC):
    """
    The ResourceParams class is an abstract class that defines shared parameters for the CRUD operations and pydantic models of the resource.

    The `serialize` attribute is a list of objects that should be included on the resource's BaseModel.
    These attributes are built using the type annotation and are a good way to include relationships in the resource's BaseModel,
    or other properties like hybrid properties or association proxies.

    !!! warning
        The `serialize` attribute is a powerful way to add features for an API consumer (e.g. a front-end UI), but it can also be dangerous.
        Serialized related objects are also, in-turn, serialized, which can lead to deeply nested JSON objects and infinite loops.
        Additionally, if the number of related objects is unknown, the response size can grow outside of the expected bounds.
        We recommend using `serialize` to expose joined types, calculated properties, or n-limited relationships;
        and use the `routed_relationships` attribute in the `ReadParams` to expose paginated related objects.

    `pop_params` can be used to exclude certain attributes from the resource's models (i.e. the base model, and CRUD-associated models).

    Attributes:
        serialize (list[str]): A list of objects to be included on the resource's BaseModel.
        pop_params (list[str]): A list of objects that should be excluded from the resource models.

    ## Example

    ```python
    from sqlalchemy.orm import Mapped, mapped_column

    from quickrest import Base, Resource


    class Student(Base, Resource):
        __tablename__ = "companies"

        first_name: Mapped[str] = mapped_column()
        last_name: Mapped[str] = mapped_column()
        dark_secret: Mapped[str] = mapped_column()

        @property
        def full_name(self) -> str:
            return f"{self.first_name} {self.last_name}"

        class resource_cfg(ResourceParams):
            serialize = ["full_name"]
            pop_params = ["dark_secret"]
    ```
    """

    serialize: list[str] = []
    pop_params: list[str] = []


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
    """
    The Resource class is a mixin that provides CRUD operations for a SQLAlchemy model.


    """

    router: APIRouter
    _sessionmaker: Callable
    __tablename__: str

    class router_cfg(RouterParams):
        pass

    class resource_cfg(ResourceParams):
        pass

    @classmethod
    def _build_basemodel(cls):
        """
        Hello

        """

        cols = [c for c in cls.__table__.columns]

        fields = {
            c.name: (
                (Optional[c.type.python_type], None)
                if c.nullable
                else (c.type.python_type, ...)
            )
            for c in cols
            if c.name not in cls.resource_cfg.pop_params
        }

        serialized_attrs = []

        for r in cls.__mapper__.relationships:
            if r.key in cls.resource_cfg.serialize:

                serialized_attrs.append(r.key)

                if len(r.remote_side) > 1:
                    # if the relationship is many-to-many, we need to use a list
                    fields[r.key] = (list[ForwardRef(r.mapper.class_.__name__)], ...)
                else:
                    # otherwise, we can just use the type of the primary key
                    fields[r.key] = (ForwardRef(r.mapper.class_.__name__), ...)

        for prop_key in set(cls.resource_cfg.serialize) - set(serialized_attrs):
            # handle associated proxy case
            if isinstance(getattr(cls, prop_key), ColumnAssociationProxyInstance):
                fields[prop_key] = (
                    getattr(cls, prop_key).remote_attr.type.python_type,
                    ...,
                )
            # handle property case
            elif isinstance(getattr(cls, prop_key), property):
                fields[prop_key] = (
                    getattr(cls, prop_key).fget.__annotations__["return"],
                    ...,
                )
            else:
                raise NotImplementedError(
                    f"Property {prop_key} of type {type(getattr(cls,prop_key))} not supported - please raise an issue or a PR!"
                )

        return create_model(cls.__name__, **fields)

    @classmethod
    def build_models(cls):

        cls.basemodel = cls._build_basemodel()

    @classmethod
    def build_router(cls) -> None:

        cls.router = APIRouter(
            prefix=cls.router_cfg.prefix or f"/{cls.__tablename__}",
            tags=cls.router_cfg.tags,
            dependencies=[Depends(fn) for fn in cls.router_cfg.dependencies],
        )

        if hasattr(cls, "read") and getattr(cls, "read_cfg", None) is not None:
            cls.read.attach_route(cls)
        if hasattr(cls, "create") and getattr(cls, "create_cfg", None) is not None:
            cls.create.attach_route(cls)
        if hasattr(cls, "delete") and getattr(cls, "delete_cfg", None) is not None:
            cls.delete.attach_route(cls)
        if hasattr(cls, "patch") and getattr(cls, "patch_cfg", None) is not None:
            cls.patch.attach_route(cls)
        if hasattr(cls, "search") and getattr(cls, "search_cfg", None) is not None:
            cls.search.attach_route(cls)

    @classmethod
    def db_generator(cls) -> Generator[Session, None, None]:
        try:
            db = cls._sessionmaker()
            yield db
        finally:
            if db is not None:
                db.close()


def build_resource(
    sessionmaker: Callable = nullraise,
    user_generator: Callable = nullreturn,
    user_token_model: Optional[BaseModel] = None,
    id_type: type = str,
    slug: bool = False,
    error_handler: Callable = default_error_handler,
) -> type:
    """
    Ths method builds a resource class with the given parameters.
    Accepts a user-defined `sessionmaker` that can be used to generate a database session.
    If using fine-grained access control, a `user_generator` can be provided to generate a user model from request data.

    ## Primary Key

    The id_type parameter can be `str`, `uuid.UUID`, or `int`, which will determine the type of the resource's ID.
    If str, resources will need to be provided with a unique string ID.
    If UUID or Int, resources will be automatically provided with a UUID or Int ID, respectively.
    If slug is True, the resource will have a slug field.

    ## Error Handling

    An `error_handler` can be provided to handle errors in the inner controller functions.
    By default, the `default_error_handler` is used.

    Args:
        sessionmaker (Callable): A callable that returns a SQLAlchemy session.
        user_generator (Callable): A callable that returns a user model.
        user_token_model (Optional[BaseModel]): A Pydantic model representing a user.
        id_type (type): The type of the resource's ID. Must be str, uuid.UUID, or int.
        slug (bool): If True, the resource will have a slug field.
        error_handler (Callable): A callable that handles errors.

    Returns:
        type: A Resource class.

    """

    ResourceBase: Type[object]

    if id_type is str:
        ResourceBase = ResourceBaseStr
    elif id_type is UUID:
        ResourceBase = ResourceBaseUUID
    elif id_type is int:
        ResourceBase = ResourceBaseInt
    else:
        raise ValueError(f"id_type must be str, uuid.UUID, or int, got {id_type}")

    class Resource(
        ResourceBase,  # type: ignore
        ResourceBaseSlug if slug else ResourceBaseSlugPass,  # type: ignore
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


class Resource(
    ResourceBaseInt if env_settings.QUICKREST_ID_TYPE == UUID else (ResourceBaseStr if env_settings.QUICKREST_ID_TYPE == str else ResourceBaseInt),  # type: ignore
    ResourceBaseSlug if env_settings.QUICKREST_USE_SLUG else ResourceBaseSlugPass,  # type: ignore
    ResourceMixin,
    CreateMixin,
    ReadMixin,
    PatchMixin,
    DeleteMixin,
    SearchMixin,
):
    """
    A default Resource class that uses an integer ID and builds a default SessionGenerator from environment variables.
    """

    _id_type = int
    _sessionmaker = default_sessionmaker()
    _user_generator = nullreturn
    _user_token = None
    _error_handler = default_error_handler
