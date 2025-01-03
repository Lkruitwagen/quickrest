# mypy: disable-error-code="name-defined"

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
    id: str | int | UUID


class ResourceBaseMeta:
    id: Union[str, UUID, int]
    __name__: str
    __tablename__: str


class User(ResourceBaseMeta):

    @classmethod
    def access_control(cls, Q: Query, user: UserTokenMeta) -> Query:
        return Q.filter(cls.id == user.id)  # type: ignore


def Publishable(user_model: ResourceBaseMeta):

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


def Private(user_model: DeclarativeBase):

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
