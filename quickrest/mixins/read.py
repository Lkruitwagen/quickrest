from abc import ABC
from functools import wraps
from inspect import Parameter, signature

from fastapi import Depends
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound

from quickrest.mixins.base import BaseMixin, RESTFactory
from quickrest.mixins.utils import classproperty


class ReadParams(ABC):
    description = None
    summary = None
    operation_id = None
    tags = None
    dependencies = []


class ReadMixin(BaseMixin):

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

        # self.response_model = self._generate_response_model(model)
        self.controller = self.controller_factory(model)
        self.ROUTE = f"/{{{model.primary_key}}}"
        # self.attach_route(model)

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
                annotation=model._user_token,
            ),
            Parameter(
                "return_db_object",
                Parameter.POSITIONAL_OR_KEYWORD,
                default=False,
                annotation=bool,
            ),
        ]

        async def inner(*args, **kwargs) -> model.basemodel:

            try:
                db = kwargs.get("db")
                primary_key = kwargs.get(model.primary_key)
                return_db_object = kwargs.get("return_db_object")
                user = kwargs.get("user")

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
                annotation=model._user_token,
            ),
        ]

        async def inner(*args, **kwargs) -> relationship.mapper.class_.basemodel:

            db = kwargs.get("db")
            primary_key = kwargs.get(model.primary_key)
            user = kwargs.get("user")
            page = kwargs.get("page")
            limit = kwargs.get("limit")

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
            summary=getattr(model, self.CFG_NAME).summary,
            tags=getattr(model, self.CFG_NAME).tags,
            operation_id=getattr(model, self.CFG_NAME).operation_id,
            methods=[self.METHOD],
            status_code=getattr(self, "SUCCESS_CODE", None) or 200,
            response_model=getattr(self, "response_model", model.basemodel),
        )

        for r in model.__mapper__.relationships:
            if r.key in model.resource_cfg.routed_relationships:
                model.router.add_api_route(
                    f"{self.ROUTE}/{r.key}",
                    self.relationship_paginated_controller(model, r),
                    description=f"Paginated relationship endpoint for {r.key}",
                    dependencies=[
                        Depends(d) for d in getattr(model, self.CFG_NAME).dependencies
                    ],
                    summary=f"Paginated relationship endpoint for {r.key}",
                    tags=getattr(model, self.CFG_NAME).tags,
                    operation_id=f"get_{r.key}_paginated",
                    methods=[self.METHOD],
                    status_code=getattr(self, "SUCCESS_CODE", None) or 200,
                    response_model=list[r.mapper.class_.basemodel],
                )
