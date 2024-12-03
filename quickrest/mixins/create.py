from functools import wraps
from inspect import Parameter, signature

from fastapi import Depends
from pydantic import BaseModel, create_model
from sqlalchemy.orm import Session

from losdos.mixins.base import BaseMixin, RESTFactory
from losdos.mixins.utils import classproperty


class CreateParams:
    description = None
    summary = None
    operation_id = None
    tags = None


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

        fields = {c.name: (c.type.python_type, ...) for c in cols}

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
