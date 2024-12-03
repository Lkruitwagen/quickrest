from abc import ABC
from functools import wraps
from inspect import Parameter, signature

from fastapi import Depends
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound

from quickrest.mixins.base import BaseMixin, RESTFactory


class DeleteParams(ABC):
    primary_key = None
    description = None
    summary = None
    operation_id = None
    tags = None


class DeleteMixin(BaseMixin):

    class delete_cfg(DeleteParams):
        pass

    @classmethod
    def build_delete(cls):
        cls.delete = DeleteFactory(cls)


class DeleteFactory(RESTFactory):

    METHOD = "DELETE"
    CFG_NAME = "delete_cfg"
    ROUTE = "/{slug}"

    def __init__(self, model):

        self.response_model = int
        self.controller = self.controller_factory(model)
        self.attach_route(model)

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
            n_deleted = Q.delete()

            if n_deleted == 0:
                raise NoResultFound

            db.commit()
            return n_deleted

        @wraps(inner)
        def f(*args, **kwargs):
            return inner(*args, **kwargs)

        # Override signature
        sig = signature(inner)
        sig = sig.replace(parameters=parameters)
        f.__signature__ = sig

        return f
