from sqlalchemy import ForeignKey, or_
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Query,
    declared_attr,
    mapped_column,
    relationship,
)


class User:

    @classmethod
    def access_control(cls, Q: Query, user) -> Query:
        return Q.filter(cls.id == user.id)


def Publishable(user_model: DeclarativeBase):

    cls_annotations = {
        user_model.__name__.lower() + "_id": Mapped[str],
        user_model.__name__.lower(): Mapped[user_model.__name__],
        "public": Mapped[bool],
    }

    @declared_attr
    def resource_owner_relationship(self) -> Mapped[user_model.__name__]:
        return relationship()

    @classmethod
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
            "access_control": access_control,
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

    @classmethod
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
            "access_control": access_control,
        },
    )

    return cls
