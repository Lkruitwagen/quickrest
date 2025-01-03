from abc import ABC
from functools import wraps
from inspect import Parameter, signature
from typing import Callable, Optional

from fastapi import Depends
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound

from quickrest.mixins.base import BaseMixin, RESTFactory
from quickrest.mixins.utils import classproperty


class ReadParams(ABC):
    """
    The `ReadParams` class can optionally be defined on the resource class.
    This class should inherit from `ReadParams` and must be called `read_cfg`.
    If `read_cfg` is set to `None`, then the read route isn't created.

    ## Example:

    ```python
    from sqlalchemy import ForeignKey
    from sqlalchemy.orm import Mapped, mapped_column, relationship

    from quickrest import Base, Resource

    from some_package.auth import must_be_admin


    class Company(Base, Resource):
        __tablename__ = "companies"

        name: Mapped[str] = mapped_column()

        class read_cfg(ReadParams):
            description = "Get a company by ID"
            summary = "Get a company by ID"
            operation_id = "get_company"
            tags = ["companies"]
            dependencies = [must_be_admin]


    class Employee(Base, Resource):
        __tablename__ = "employees"

        name: Mapped[str] = mapped_column()
        company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))

        # set read_cfg to None to disable the read route
        read_cfg = None
    ```

    Attributes:
        description (str, optional): Description of the endpoint. Optional, defaults to `None`.
        summary (str, optional): Summary of the endpoint. Optional, defaults to `get {resource_name}`.
        operation_id (str, optional): Operation ID of the endpoint. Optional, defaults to `None`.
        tags (list[str], optional): Tags for the endpoint. Optional, defaults to `None`.
        dependencies (list[Callable]): Injectable callable dependencies for the endpoint. Optional, defaults to `[]`.
        routed_relationships (list[str]: List of relationship names to create paginated endpoints for. Strings must match the relationship attributes. Optional, defaults to `[]`.

    """

    description: Optional[str] = None
    summary: Optional[str] = None
    operation_id: Optional[str] = None
    tags: Optional[list[str]] = None
    dependencies: list[Callable] = []

    routed_relationships: list[str] = []


class ReadMixin(BaseMixin):
    """
    This mixin is automatically inherited by the `Resource` class and provides endpoints for reading resources.
    Multiple endpoints are created for reading resources, including a `GET` endpoint for a single resource, and paginated endpoints for each relationship of the resource.

    ## Endpoints - Read One

        GET /{resource_name}/{primary_key}

    The primary key is the `id` of the resource, unless the resource has a `slug` primary key, in which case the primary key is the `slug`.

    | Property | Description |
    | :--- | :---- |
    | Method | `GET` |
    | Route | `/{resource_name}/{primary_key}` |
    | Request  | Path: `{primary_key}` </br> Query: `<none>` </br> Body: `<none>` |
    | Success Response | 200 OK: Resource [BaseModel](resource.md#BaseModel) |


    ## Endpoints - Read Related Resources

        GET /{resource_name}/{primary_key}/{relationship_name}?limit=10&page=0

    The ReadMixin also provides paginated endpoints for each relationship of the resource, with a `page` and `limit` query parameter:

    | Property | Description |
    | :--- | :---- |
    | Method | `GET` |
    | Route | `/{resource_name}/{primary_key}/{related_resource_name}` |
    | Request  | Path: `{primary_key}` </br> Query: `limit [int]; page [int]` </br> Body: `<none>` |
    | Success Response | 200 OK: Resource [PaginatedBaseModel](resource.md#PaginatedBaseModel) |


    ## Example:

    A simple example of how to define a one-to-many relationship between a `Parent` and `Child` resource, and create a paginated endpoint for the `children` relationship.

    ```python
    from sqlalchemy import ForeignKey
    from sqlalchemy.orm import Mapped, mapped_column, relationship

    from quickrest import Base, Resource


    class Parent(Base, Resource):
        __tablename__ = "parents"

        children: Mapped[list["Child"]] = relationship()

        class read_cfg(ReadParams):
            routed_relationships = ["children"]


    class Child(Base, Resource):

        __tablename__ = "children"

        parent_id: Mapped[int] = mapped_column(ForeignKey("parents.id"))
    ```
    """

    _read = None

    class read_cfg(ReadParams):
        pass

    @classproperty
    def read(cls):
        if cls._read is None:
            cls._read = ReadFactory(cls)
        return cls._read


class ReadFactory(RESTFactory):

    METHOD = "GET"
    CFG_NAME = "read_cfg"

    def __init__(self, model):

        self.controller = self.controller_factory(model)
        self.ROUTE = f"/{{{model.primary_key}}}"

    def controller_factory(self, model):

        primary_key_type = str if model.primary_key == "slug" else model._id_type

        parameters = [
            Parameter(
                model.primary_key,
                Parameter.POSITIONAL_OR_KEYWORD,
                default=...,
                annotation=primary_key_type,
            ),
            Parameter(
                "db",
                Parameter.POSITIONAL_OR_KEYWORD,
                default=Depends(model.db_generator),
                annotation=Session,
            ),
            Parameter(
                "user",
                Parameter.POSITIONAL_OR_KEYWORD,
                default=Depends(model._user_generator),
                annotation=model._user_generator.__annotations__["return"],
            ),
            Parameter(
                "return_db_object",
                Parameter.POSITIONAL_OR_KEYWORD,
                default=False,
                annotation=bool,
            ),
        ]

        async def inner(*args, **kwargs) -> model.basemodel:  # type: ignore

            try:
                db = kwargs["db"]
                primary_key = kwargs[model.primary_key]
                return_db_object = kwargs["return_db_object"]
                user = kwargs["user"]

                Q = db.query(model)
                Q = Q.filter(getattr(model, model.primary_key) == primary_key)
                if hasattr(model, "access_control"):
                    Q = model.access_control(Q, user)
                obj = Q.first()

                if not obj:
                    raise NoResultFound

                if return_db_object:
                    return obj

                return model.basemodel.model_validate(obj, from_attributes=True)
            except Exception as e:
                raise model._error_handler(e)

        @wraps(inner)
        async def f(*args, **kwargs):
            return await inner(*args, **kwargs)

        # Override signature
        sig = signature(inner)
        sig = sig.replace(parameters=parameters)
        f.__signature__ = sig

        return f

    def relationship_paginated_controller(self, model, relationship):

        primary_key_type = str if model.primary_key == "slug" else model._id_type

        parameters = [
            Parameter(
                model.primary_key,
                Parameter.POSITIONAL_OR_KEYWORD,
                default=...,
                annotation=primary_key_type,
            ),
            Parameter(
                "limit", Parameter.POSITIONAL_OR_KEYWORD, default=10, annotation=int
            ),
            Parameter(
                "page", Parameter.POSITIONAL_OR_KEYWORD, default=0, annotation=int
            ),
            Parameter(
                "db",
                Parameter.POSITIONAL_OR_KEYWORD,
                default=Depends(model.db_generator),
                annotation=Session,
            ),
            Parameter(
                "user",
                Parameter.POSITIONAL_OR_KEYWORD,
                default=Depends(model._user_generator),
                annotation=model._user_generator.__annotations__["return"],
            ),
        ]

        async def inner(*args, **kwargs) -> relationship.mapper.class_.basemodel:  # type: ignore

            db = kwargs["db"]
            primary_key = kwargs[model.primary_key]
            user = kwargs["user"]
            page = kwargs["page"]
            limit = kwargs["limit"]

            offset = page * limit

            Q = db.query(relationship.mapper.class_).join(model)
            Q = Q.filter(getattr(model, model.primary_key) == primary_key)
            if hasattr(model, "access_control"):
                Q = model.access_control(Q, user)
            Q = Q.limit(limit).offset(offset)

            objs = Q.all()

            return [
                relationship.mapper.class_.basemodel.model_validate(
                    obj, from_attributes=True
                )
                for obj in objs
            ]

        @wraps(inner)
        async def f(*args, **kwargs):
            return await inner(*args, **kwargs)

        # Override signature
        sig = signature(inner)
        sig = sig.replace(parameters=parameters)
        f.__signature__ = sig

        return f

    def attach_route(self, model) -> None:

        # Overwrite this from the base class

        # same as base class, add base router
        model.router.add_api_route(
            self.ROUTE,
            self.controller,
            description=getattr(model, self.CFG_NAME).description,
            dependencies=[
                Depends(d) for d in getattr(model, self.CFG_NAME).dependencies
            ],
            summary=getattr(model, self.CFG_NAME).summary
            or self.METHOD.lower() + " " + model.__name__.lower(),
            tags=getattr(model, self.CFG_NAME).tags or [model.__name__],
            operation_id=getattr(model, self.CFG_NAME).operation_id,
            methods=[self.METHOD],
            status_code=getattr(self, "SUCCESS_CODE", None) or 200,
            response_model=getattr(self, "response_model", model.basemodel),
        )

        # add paginated relationship routes for each relationship
        for r in model.__mapper__.relationships:
            if r.key in getattr(model, self.CFG_NAME).routed_relationships:
                model.router.add_api_route(
                    f"{self.ROUTE}/{r.key}",
                    self.relationship_paginated_controller(model, r),
                    description=f"Paginated relationship endpoint for {r.key}",
                    dependencies=[
                        Depends(d) for d in getattr(model, self.CFG_NAME).dependencies
                    ],
                    summary=f"Paginated relationship endpoint for {r.key}",
                    tags=getattr(model, self.CFG_NAME).tags or [model.__name__],
                    operation_id=f"get_{r.key}_paginated",
                    methods=[self.METHOD],
                    status_code=getattr(self, "SUCCESS_CODE", None) or 200,
                    response_model=list[r.mapper.class_.basemodel],  # type: ignore
                )
