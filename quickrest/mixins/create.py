from functools import wraps
from inspect import Parameter, signature
from typing import Any, Callable, Optional

from fastapi import Depends
from pydantic import BaseModel, create_model
from sqlalchemy.orm import Session

from quickrest.mixins.base import BaseMixin, RESTFactory
from quickrest.mixins.utils import classproperty


class CreateParams:
    description: Optional[str] = None
    summary: Optional[str] = None
    operation_id: Optional[str] = None
    tags: Optional[list[str]] = None
    dependencies: list[Callable] = []


class CreateMixin(BaseMixin):

    _create = None

    class create_cfg(CreateParams):
        pass

    @classproperty
    def create(cls):
        if cls._create is None:
            cls._create = CreateFactory(cls)
        return cls._create


class CreateFactory(RESTFactory):

    METHOD = "POST"
    CFG_NAME = "create_cfg"
    ROUTE = ""
    SUCCESS_CODE = 201

    def __init__(self, model):

        self.input_model = self._generate_input_model(model)
        self.controller = self.controller_factory(model)

    def _generate_input_model(self, model) -> BaseModel:
        cols = [c for c in model.__table__.columns]

        primary_fields = {
            c.name: (
                (Optional[c.type.python_type], None)
                if c.nullable
                else (c.type.python_type, ...)
            )
            for c in cols
            # filter ID field if it's not a (user-provided) string
            if ((c.name != "id") or (c.type.python_type == str))
        }

        # map relationship fields
        relationship_fields = {}
        for r in model.__mapper__.relationships:
            if len(r.remote_side) > 1:
                # if the relationship is many-to-many, we need to use a list
                relationship_fields[r.key] = (Optional[list[str]], None)
            else:
                # otherwise, we can just use the type of the primary key
                relationship_fields[r.key] = (Optional[str], None)

        fields: Any = {**primary_fields, **relationship_fields}

        return create_model(str("Create" + model.__name__), **fields)

    def controller_factory(self, model, **kwargs) -> Callable:
        parameters = [
            Parameter(
                self.input_model.__name__.lower(),
                Parameter.POSITIONAL_OR_KEYWORD,
                default=...,
                annotation=self.input_model,
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

        async def inner(*args, **kwargs) -> model:
            db = kwargs["db"]
            body = kwargs[self.input_model.__name__.lower()]
            user = kwargs["user"]

            obj = model(
                **{
                    c.name: getattr(body, c.name)
                    for c in model.__table__.columns
                    if ((c.name != "id") or (c.type.python_type == str))
                }
            )

            for r in model.__mapper__.relationships:

                related_ids = getattr(body, r.key)

                if related_ids:

                    if isinstance(related_ids, list):
                        related_objs = [
                            await r.mapper.class_.read.controller(
                                **{
                                    "db": db,
                                    r.mapper.class_.primary_key: primary_key,
                                    "return_db_object": True,
                                    "user": user,
                                }
                            )
                            for primary_key in related_ids
                        ]
                    else:
                        related_objs = r.mapper.class_.read.controller(
                            **{
                                "db": db,
                                r.mapper.class_.primary_key: related_ids,
                                "return_db_object": True,
                                "user": user,
                            }
                        )

                    setattr(obj, r.key, related_objs)

            db.add(obj)
            db.commit()
            db.refresh(obj)

            return model.basemodel.model_validate(obj, from_attributes=True)

        @wraps(inner)
        async def f(*args, **kwargs):
            return await inner(*args, **kwargs)

        # Override signature
        sig = signature(inner)
        sig = sig.replace(parameters=parameters)
        f.__signature__ = sig  # type: ignore

        return f
