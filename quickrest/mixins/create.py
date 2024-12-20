from functools import wraps
from inspect import Parameter, signature
from typing import Optional

from fastapi import Depends
from pydantic import BaseModel, create_model
from sqlalchemy.orm import Session

from quickrest.mixins.base import BaseMixin, RESTFactory
from quickrest.mixins.utils import classproperty


class CreateParams:
    description = None
    summary = None
    operation_id = None
    tags = None
    dependencies = []


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
        # self.attach_route(model)

    def _generate_input_model(self, model) -> BaseModel:
        cols = [c for c in model.__table__.columns]

        primary_fields = {
            c.name: (c.type.python_type, ...)
            for c in cols
            # filter ID field if it's not a (user-provided) string
            if ((c.name != "id") or (c.type.python_type == str))
        }

        # map relationship fields
        relationship_fields = {}
        for r in model.__mapper__.relationships:
            if len(r.remote_side) > 1:
                # if the relationship is many-to-many, we need to use a list
                # TODO: is this required?
                relationship_fields[r.key] = (Optional[list[str]], None)
            else:
                # otherwise, we can just use the type of the primary key
                relationship_fields[r.key] = (Optional[str], None)

        fields = {**primary_fields, **relationship_fields}

        return create_model("CREATE" + model.__name__, **fields)

    def controller_factory(self, model, **kwargs) -> callable:
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
        ]

        async def inner(*args, **kwargs) -> model:
            db = kwargs.get("db")
            body = kwargs.get(self.input_model.__name__.lower())

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
                                db=db, id=id, return_db_object=True
                            )
                            for id in related_ids
                        ]
                    else:
                        related_objs = r.mapper.class_.read.controller(
                            db=db, id=related_ids, return_db_object=True
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
        f.__signature__ = sig

        return f
