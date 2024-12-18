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
    ROUTE = "/{id}"

    def __init__(self, model):

        # self.response_model = self._generate_response_model(model)
        self.controller = self.controller_factory(model)
        # self.attach_route(model)

    def controller_factory(self, model):

        parameters = [
            Parameter(
                "id", Parameter.POSITIONAL_OR_KEYWORD, default=..., annotation=str
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
                "reurn_db_object",
                Parameter.POSITIONAL_OR_KEYWORD,
                default=False,
                annotation=bool,
            ),
        ]

        async def inner(*args, **kwargs) -> model.basemodel:

            try:
                db = kwargs.get("db")
                primary_key = kwargs.get("id")
                return_db_object = kwargs.get("return_db_object")
                user = kwargs.get("user")

                Q = db.query(model)
                Q = Q.filter(model.id == primary_key)
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
