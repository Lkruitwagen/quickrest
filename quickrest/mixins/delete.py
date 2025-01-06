from abc import ABC
from functools import wraps
from inspect import Parameter, signature
from typing import Callable, Optional

from fastapi import Depends
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound

from quickrest.mixins.base import BaseMixin, RESTFactory
from quickrest.mixins.utils import classproperty


class DeleteConfig(ABC):
    """
    The `DeleteConfig` class can optionally be defined on the resource class.
    This class should inherit from `DeleteConfig` and must be called `delete_cfg`.
    If `delete_cfg` is set to `None`, then the delete route isn't created.
    The delete route is used for deleting a single resource object.

    ## Example:

    This example shows a typical use case - resources can only be deleted by admin users.

    ```python
    from sqlalchemy.orm import Mapped, mapped_column

    from quickrest import Base, Resource, DeleteConfig

    from some_package.auth import is_admin_user


    class Employee(Base, Resource):
        __tablename__ = "employees"

        name: Mapped[str] = mapped_column()
        job_title: Mapped[str] = mapped_column()

        class patch_cfg(DeleteConfig):
            description = "delete an employee"
            summary = "delete an employee"
            operation_id = "delete_employee"
            tags = ["employees"]
            dependencies = [is_admin_user]
    ```

    Attributes:
        description (str, optional): Description of the endpoint. Optional, defaults to `None`.
        summary (str, optional): Summary of the endpoint. Optional, defaults to `get {resource_name}`.
        operation_id (str, optional): Operation ID of the endpoint. Optional, defaults to `None`.
        tags (list[str], optional): Tags for the endpoint. Optional, defaults to `None`.
        dependencies (list[Callable]): Injectable callable dependencies for the endpoint. Optional, defaults to `[]`.

    """

    description: Optional[str] = None
    summary: Optional[str] = None
    operation_id: Optional[str] = None
    tags: Optional[list[str]] = None
    dependencies: list[Callable] = []


class DeleteMixin(BaseMixin):
    """
    This mixin is automatically inherited by the `Resource` class and provides endpoints for deleting resources.
    The delete method is a `DELETE` request to the resource endpoint with the `primary_key` (i.e. slug or id) in the path.
    The response model is the number of resources deleted, which should always be `1` if the resource exists.

    ## Endpoint - Delete Resource

        DELETE /{resource_name}/{primary_key}

    The primary key is the `id` of the resource, unless the resource has a `slug` primary key, in which case the primary key is the `slug`.

    | Property | Description |
    | :--- | :---- |
    | Method | `DELETE` |
    | Route | `/{resource_name}/{primary_key}` |
    | Request  | Path: `{primary_key}` </br> Query: `<none>` </br> Body: `<none>` |
    | Success Response | 200 OK: `int` |

    """

    _delete = None

    class delete_cfg(DeleteConfig):
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
                annotation=model._user_generator.__annotations__["return"],
            ),
        ]

        def inner(*args, **kwargs) -> int:

            try:
                db = kwargs["db"]
                primary_key = kwargs[model.primary_key]
                user = kwargs["user"]

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
