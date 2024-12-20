from abc import ABC
from functools import wraps
from inspect import Parameter, signature

from fastapi import Depends
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound

from quickrest.mixins.base import BaseMixin, RESTFactory
from quickrest.mixins.utils import classproperty


class DeleteParams(ABC):
    primary_key = None
    description = None
    summary = None
    operation_id = None
    tags = None
    dependencies = []


class DeleteMixin(BaseMixin):

    _delete = None

    class delete_cfg(DeleteParams):
        pass

    @classproperty
    def delete(cls):
        if cls._delete is None:
            cls._delete = DeleteFactory(cls)
        return cls._delete


class DeleteFactory(RESTFactory):

    METHOD = "DELETE"
    CFG_NAME = "delete_cfg"

    def __init__(self, model):

        self.response_model = int
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
                annotation=model._user_token,
            ),
        ]

        def inner(*args, **kwargs) -> self.response_model:

            try:
                db = kwargs.get("db")
                primary_key = kwargs.get(model.primary_key)
                user = kwargs.get("user")

                Q = db.query(model)
                Q = Q.filter(getattr(model, model.primary_key) == primary_key)
                if hasattr(model, "access_control"):
                    Q = model.access_control(Q, user)

                n_deleted = Q.delete()

                if n_deleted == 0:
                    raise NoResultFound

                db.commit()
                return n_deleted
            except Exception as e:
                raise model._error_handler(e)

        @wraps(inner)
        def f(*args, **kwargs):
            return inner(*args, **kwargs)

        # Override signature
        sig = signature(inner)
        sig = sig.replace(parameters=parameters)
        f.__signature__ = sig

        return f
