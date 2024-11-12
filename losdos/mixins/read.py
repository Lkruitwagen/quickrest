from abc import ABC
from functools import wraps
from inspect import Parameter, signature

from fastapi import Depends
from pydantic import BaseModel, create_model
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound

from losdos.mixins.base import BaseMixin, RESTFactory


class ReadParams(ABC):
    primary_key = None
    description = None
    summary = None
    operation_id = None
    tags = None


class ReadMixin(BaseMixin):

    class read_cfg(ReadParams):
        pass

    @classmethod
    def build_read(cls):
        cls.read = ReadFactory(cls)


class ReadFactory(RESTFactory):

    METHOD = "GET"
    CFG_NAME = "read_cfg"
    ROUTE = "/{slug}"

    def __init__(self, model):

        self.response_model = self._generate_response_model(model)
        self.controller = self.controller_factory(model)
        self.attach_route(model)

    def _generate_response_model(self, model) -> BaseModel:
        cols = [c for c in model.__table__.columns]
        return create_model(
            model.__name__, **{c.name: (c.type.python_type, ...) for c in cols}
        )

    def controller_factory(self, model):

        parameters = [
            Parameter(
                "slug", Parameter.POSITIONAL_OR_KEYWORD, default=..., annotation=str
            ),
            Parameter(
                "db",
                Parameter.POSITIONAL_OR_KEYWORD,
                default=Depends(model.db_generator),
                annotation=Session,
            ),
        ]

        def inner(*args, **kwargs) -> self.response_model:

            db = kwargs.get("db")
            primary_key = kwargs.get("slug")

            Q = db.query(model)
            Q = Q.filter(model.slug == primary_key)
            obj = Q.first()

            if not obj:
                raise NoResultFound

            return self.response_model.model_validate(obj)

        @wraps(inner)
        def f(*args, **kwargs):
            return inner(*args, **kwargs)

        # Override signature
        sig = signature(inner)
        sig = sig.replace(parameters=parameters)
        f.__signature__ = sig

        return f
