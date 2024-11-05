from functools import wraps
from inspect import Parameter, signature

from fastapi import Depends
from pydantic import BaseModel, create_model
from sqlalchemy.orm import Session

from losdos.mixins.base import BaseMixin, RESTFactory


class CreateParams:
    description = None
    summary = None
    operation_id = None
    tags = None


class CreateMixin(BaseMixin):

    class create_cfg(CreateParams):
        pass

    @classmethod
    def build_create(cls):
        cls.create = CreateFactory(cls)


class CreateFactory(RESTFactory):

    METHOD = "POST"
    CFG_NAME = "create_cfg"
    ROUTE = ""

    def __init__(self, model):

        self.input_model = self._generate_input_model(model)
        self.response_model = self._generate_response_model(model)
        self.controller = self.controller_factory(model)
        self.attach_route(model)

    def _generate_input_model(self, model) -> BaseModel:
        cols = [c for c in model.__table__.columns]

        return create_model(
            model.__name__,
            **{c.name: (c.type.python_type, ...) for c in cols if c.name not in ["id"]},
        )

    def _generate_response_model(self, model) -> BaseModel:
        cols = [c for c in model.__table__.columns]
        return create_model(
            model.__name__, **{c.name: (c.type.python_type, ...) for c in cols}
        )

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

        def inner(*args, **kwargs) -> model:
            db = kwargs.get("db")
            body = kwargs.get(self.input_model.__name__.lower())

            obj = model(**body.model_dump())

            db.add(obj)
            db.commit()
            db.refresh(obj)
            return obj

        @wraps(inner)
        def f(*args, **kwargs):
            return inner(*args, **kwargs)

        # Override signature
        sig = signature(inner)
        sig = sig.replace(parameters=parameters)
        f.__signature__ = sig

        return f
