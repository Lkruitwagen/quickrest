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


class PatchConfig(ABC):
    """
    The `PatchConfig` class can optionally be defined on the resource class.
    This class should inherit from `PatchConfig` and must be called `patch_cfg`.
    If `patch_cfg` is set to `None`, then the patch route isn't created.

    The `PatchConfig` class can be used to limit which parameters are patchable on the resource.
    Parameters listed in `patchable_params` can be patched, while parameters listed in `nonpatchable_params` cannot be patched.
    Only one of `patchable_params` and `nonpatchable_params` should be defined.
    If both are defined, the difference between the sets (patchable_params - nonpatchable_params) will be used.
    Non-patchable parameters retain their values from the original object.

    ## Example:

    In this example, only the `job_title` parameter can be patched on the `Employee` resource.

    ```python
    from sqlalchemy.orm import Mapped, mapped_column

    from quickrest import Base, Resource, PatchConfig

    from some_package.auth import authenticate_user


    class Employee(Base, Resource):
        __tablename__ = "employees"

        name: Mapped[str] = mapped_column()
        job_title: Mapped[str] = mapped_column()

        class patch_cfg(PatchConfig):
            description = "update an employee"
            summary = "update an employee"
            operation_id = "update_employee"
            tags = ["employees"]
            dependencies = [authenticate_user]

            patchable_params = ["job_title"]
    ```

    Attributes:
        description (str, optional): Description of the endpoint. Optional, defaults to `None`.
        summary (str, optional): Summary of the endpoint. Optional, defaults to `get {resource_name}`.
        operation_id (str, optional): Operation ID of the endpoint. Optional, defaults to `None`.
        tags (list[str], optional): Tags for the endpoint. Optional, defaults to `None`.
        dependencies (list[Callable]): Injectable callable dependencies for the endpoint. Optional, defaults to `[]`.
        patchable_params ( Optional[list[str]): A list of parameters that can be patched. Optional, defaults to `None`.
        nonpatchable_params ( Optional[list[str]): A list of parameters that cannot be patched. Optional, defaults to `None`.

    """

    # router method
    description: Optional[str] = None
    summary: Optional[str] = None
    operation_id: Optional[str] = None
    tags: Optional[list[str]] = None
    dependencies: list[Callable] = []

    # patch method
    patchable_params: Optional[list[str]] = None
    nonpatchable_params: Optional[list[str]] = None


class PatchMixin(BaseMixin):
    """
    This mixin is automatically inherited by the `Resource` class and provides endpoints for updating resources.
    The update method is a `PATCH` request to the resource endpoint, and the whole object does not need to be sent in the request body, just the fields to update.
    The mixin also builds a Pydantic model for the input body of the patch endpoint.

    ## PatchModel

    The `PatchModel` is a Pydantic model build using the fields of the sqlalchemy model.
    The model only includes field that are patchable (and not non-patchable), as defined in `PatchConfig`.
    All fields are optional, and only the fields that are included in the request body will be updated.
    Object IDs are never patchable.

    For relationship fields, many-to-many related objects can be patched by specifying a list of primary keys.
    This overwrites the existing relationships.
    One-to-many related objects can be specified by a single primary key, suffixed with `_id`.

    === "SQLAlchemy Resource"

        ```python
        from sqlalchemy.orm import Mapped, mapped_column

        from quickrest import Base, Resource, PatchConfig


        class Employee(Base, Resource):
            __tablename__ = "employees"

            name: Mapped[str] = mapped_column()
            job_title: Mapped[str] = mapped_column()

            class patch_cfg(PatchConfig):
                patchable_params = ["job_title"]
        ```

    === "Equivalent Pydantic Model"

        ```python
        from pydantic import BaseModel


        class PatchEmployee(BaseModel):
            job_title: str | None
        ```

    ## Endpoint - Create Resource

        PATCH /{resource_name}/{primary_key}

    The primary key is the `id` of the resource, unless the resource has a `slug` primary key, in which case the primary key is the `slug`.

    | Property | Description |
    | :--- | :---- |
    | Method | `PATCH` |
    | Route | `/{resource_name}/{primary_key}` |
    | Request  | Path: `{primary_key}` </br> Query: `<none>` </br> Body: Resource PatchModel |
    | Success Response | 200 OK: Resource [BaseModel](resource.md#quickrest.mixins.resource.ResourceMixin._build_basemodel) |

    """

    _patch = None

    class patch_cfg(PatchConfig):
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

        patchable_params = (
            set(getattr(model, "patchable_params", None) or fields.keys())
            - set(getattr(model, "nonpatchable_params", None) or [])
            - {"id"}
        )

        fields = {k: v for k, v in fields.items() if k in patchable_params}

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
                annotation=model._user_generator.__annotations__["return"],
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
