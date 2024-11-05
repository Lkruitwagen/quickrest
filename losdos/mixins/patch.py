from abc import ABC
from functools import wraps
from inspect import Parameter, signature
from typing import Optional

from fastapi import Depends
from pydantic import BaseModel, create_model
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound

from losdos.mixins.base import BaseMixin, RESTFactory


class PatchParams(ABC):
    primary_key = None
    patchable_params = None
    nonpatchable_params = None

    # router method
    description = None
    summary = None
    operation_id = None
    tags = None


class PatchMixin(BaseMixin):

    class patch_cfg(PatchParams):
        pass

    @classmethod
    def build_update(cls):
        cls.patch = PatchFactory(cls)


class PatchFactory(RESTFactory):

    METHOD = "PATCH"
    CFG_NAME = "patch_cfg"
    ROUTE = "/{slug}"

    def __init__(self, model):
        self.input_model = self._generate_input_model(model)
        self.response_model = self._generate_response_model(model)
        self.controller = self.controller_factory(model)
        self.attach_route(model)

    def _generate_input_model(self, model) -> BaseModel:
        cols = [c for c in model.__table__.columns]

        return create_model(
            model.__name__,
            **{
                c.name: (Optional[c.type.python_type], None)
                for c in cols
                if c.name not in ["id"]
            },
        )

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
                "patch",
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

        def inner(*args, **kwargs) -> self.response_model:

            db = kwargs.get("db")
            slug = kwargs.get("slug")
            patch = kwargs.get("patch")

            Q = db.query(model)
            Q = Q.filter(model.slug == slug)
            obj = Q.first()

            if not obj:
                raise NoResultFound

            for name, val in patch.model_dump().items():
                if val is not None:
                    setattr(obj, name, val)

            db.commit()
            db.refresh(obj)

            return self.response_model.model_validate(obj)

        @wraps(inner)
        def f(*args, **kwargs):
            return inner(*args, **kwargs)

        # Override signature
        sig = signature(inner)
        sig = sig.replace(parameters=parameters)
        f.__signature__ = sig

        return f
