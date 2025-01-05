# mypy: disable-error-code="name-defined"

"""
QuickRest provides fine-grained access control for resources, which is to say, it allows developers to define which users can access which rows in the database.
This is achieved by defining a `BaseUserModel` and a user-defined function that returns the current user.
The `BaseUserModel` should be subclassed by the user model and should provide a `id` field.
The user-defined function should return an instance of the `BaseUserModel` with the current user's id.

Then, Resource classes can be mixed-in with either the Private or Publishable access-control mixins.
These mixins use the current user object to provide additional filtering on all queries made to the resource table.
Fine-grained access control can be combined with route-level access control via dependency-injection to provide a secure API.

## Example:

The following example shows how to use the `BaseUserModel` and a user-defined function to provide fine-grained access control on resources:

```python
import logging
from datetime import date
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import ForeignKey, create_engine, event
from sqlalchemy.orm import Mapped, mapped_column, relationship, sessionmaker

from quickrest import Base, BaseUserModel, make_private, User, Resource

from user_defined_code import decode_token


class UserToken(BaseUserModel):
    id: str
    permissions: list[str]


async def get_current_user(request: Request) -> UserToken:

    # write your own auth logic here - normally decoding tokens etc
    _id, permissions = decode_token(request.headers.get("Authorization", ""))

    return UserToken(
        id=_id,
        permissions=permissions,
    )


class Owner(
    Base,
    Resource,
    User,
):
    __tablename__ = "owners"
    name: Mapped[str] = mapped_column()

    pets: Mapped[list["Pet"]] = relationship(back_populates="owner")

    class read_cfg(ReadParams):
        routed_relationships = ["pets"]


class Pet(Base, Resource, make_publishable(user_model=Owner)):
    __tablename__ = "pets"

    name: Mapped[str] = mapped_column()
    species: Mapped[str] = mapped_column()
```
"""

from typing import Union
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import ForeignKey, or_
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Query,
    declared_attr,
    mapped_column,
    relationship,
)


class UserTokenMeta:
    id: str


class BaseUserModel(BaseModel):
    """
    A basemodel for authenticated users.

    Developers using fine-grained access control should subclass this model and provide a `id` field.
    This model should be returned by an authentication dependency, that, for example, decode a JWT token and returns the user id.
    There is only one require attribute, which is the user id.

    Attributes:
        id (str | int | UUID): The user id.
    """

    id: str | int | UUID


class ResourceBaseMeta:
    id: Union[str, UUID, int]
    __name__: str
    __tablename__: str


class User(ResourceBaseMeta):
    """
    The User mixin that identifies the user model and provides access control for the user resource.

    Provides a classmethod `access_control` that filters the query to only include resources with the same id as the user.
    """

    @classmethod
    def access_control(cls, Q: Query, user: UserTokenMeta) -> Query:
        return Q.filter(cls.id == user.id)  # type: ignore


def make_publishable(user_model: ResourceBaseMeta):
    """
    Builds the `Publishable` mixin, referencing the defined `User` class.
    The `Publishable` mixin provides a `public (boolean)` column that can be used to mark resources as readable by all users,
    and an `<owner>_id` column that references the user that owns the resource.
    Public resources can still be protected at the route-level, and remain only editable by the resource owner.
    A classmethod `access_control` that filters incoming queries to include only resources with the same `<owner>_id` as the requesting user or resources marked as public.

    Parameters:
        user_model (ResourceBaseMeta): The user model to reference in the mixin.

    Returns:
        type: The Publishable mixin class.
    """

    cls_annotations = {
        user_model.__name__.lower() + "_id": Mapped[str],
        user_model.__name__.lower(): Mapped[user_model.__name__],
        "public": Mapped[bool],
    }

    @declared_attr
    def resource_owner_relationship(self) -> Mapped[user_model.__name__]:
        return relationship()

    def access_control(cls, Q: Query, user) -> Query:
        return Q.filter(
            or_(
                (getattr(cls, user_model.__name__.lower() + "_id") == user.id),
                (cls.public == True),
            )
        )

    cls = type(
        "Publishable",
        (object,),
        {
            # class topmatter
            "__doc__": "class created by type",
            # column type annotations
            "__annotations__": cls_annotations,
            # class attributes (i.e. columns)
            user_model.__name__.lower()
            + "_id": mapped_column(ForeignKey(user_model.__tablename__ + ".id")),
            "public": mapped_column(),
            # class methods (inc. relationships)
            user_model.__name__.lower(): resource_owner_relationship,
            "access_control": classmethod(access_control),
        },
    )

    return cls


def make_private(user_model: DeclarativeBase):
    """
    Builds the `Private` mixin, referencing the defined `User` class.
    The `Private` mixin provides a `<owner>_id` column that references the user that owns the resource.
    Private resources can only be read (or patched, deleted) by the resource owner.
    A classmethod `access_control` that filters incoming queries to filter `<owner>_id` to the same id as the requesting user.

    Parameters:
        user_model (ResourceBaseMeta): The user model to reference in the mixin.

    Returns:
        type: The Private mixin class.
    """

    cls_annotations = {
        user_model.__name__.lower() + "_id": Mapped[str],
        user_model.__name__.lower(): Mapped[user_model.__name__],
    }

    @declared_attr
    def resource_owner_relationship(self) -> Mapped[user_model.__name__]:
        return relationship()

    def access_control(cls, Q: Query, user) -> Query:
        return Q.filter(getattr(cls, user_model.__name__.lower() + "_id") == user.id)

    cls = type(
        "Publishable",
        (object,),
        {
            # class topmatter
            "__doc__": "class created by type",
            # column type annotations
            "__annotations__": cls_annotations,
            # class attributes (i.e. columns)
            user_model.__name__.lower()
            + "_id": mapped_column(ForeignKey(user_model.__tablename__ + ".id")),
            # class methods (inc. relationships)
            user_model.__name__.lower(): resource_owner_relationship,
            "access_control": classmethod(access_control),
        },
    )

    return cls
