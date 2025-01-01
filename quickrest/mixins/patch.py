from abc import ABC
from functools import wraps
from inspect import Parameter, signature
from typing import Any, Callable, Optional

from fastapi import Depends
from pydantic import BaseModel, create_model
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound

from quickrest.mixins.base import BaseMixin, RESTFactory
from quickrest.mixins.utils import classproperty


class PatchParams(ABC):
    primary_key: Optional[str] = None
    patchable_params: Optional[list[str]] = None
    nonpatchable_params: Optional[list[str]] = None
    dependencies: list[Callable] = []

    # router method
    description: Optional[str] = None
    summary: Optional[str] = None
    operation_id: Optional[str] = None
    tags: Optional[list[str]] = None


class PatchMixin(BaseMixin):

    _patch = None

    class patch_cfg(PatchParams):
        pass

    @classproperty
    def patch(cls):
        if cls._patch is None:
            cls._patch = PatchFactory(cls)
        return cls._patch


class PatchFactory(RESTFactory):

    METHOD = "PATCH"
    CFG_NAME = "patch_cfg"

    def __init__(self, model):
        self.input_model = self._generate_input_model(model)
        self.controller = self.controller_factory(model)
        self.ROUTE = f"/{{{model.primary_key}}}"

    def _generate_input_model(self, model) -> BaseModel:

        cols = [c for c in model.__table__.columns]

        primary_fields = {
            c.name: (Optional[c.type.python_type], None)
            for c in cols
            # filter ID field if it's not a (user-provided) string
            if c.name != "id"
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

        fields: Any = {**primary_fields, **relationship_fields}

        return create_model("Patch" + model.__name__, **fields)

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
            Parameter(
                "user",
                Parameter.POSITIONAL_OR_KEYWORD,
                default=Depends(model._user_generator),
                annotation=model._user_token,
            ),
        ]

        async def inner(*args, **kwargs) -> model:

            try:
                db = kwargs["db"]
                primary_key = kwargs[model.primary_key]
                user = kwargs["user"]
                patch = kwargs["patch"]

                Q = db.query(model)
                Q = Q.filter(getattr(model, model.primary_key) == primary_key)
                if hasattr(model, "access_control"):
                    Q = model.access_control(Q, user)

                obj = Q.first()

                if not obj:
                    raise NoResultFound

                # patch column attributes
                for c in model.__table__.columns:
                    if c.name != "id":
                        if getattr(patch, c.name):
                            setattr(obj, c.name, getattr(patch, c.name))

                # patch relationship attributes
                for r in model.__mapper__.relationships:

                    if getattr(patch, r.key) is not None:

                        related_ids = getattr(patch, r.key)

                        # todo: handle slug case
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
                                    r.mapper.class_.primary_key: primary_key,
                                    "return_db_object": True,
                                    "user": user,
                                }
                            )

                        setattr(obj, r.key, related_objs)

                db.commit()
                db.refresh(obj)

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
