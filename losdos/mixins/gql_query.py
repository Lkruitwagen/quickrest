from abc import ABC

import strawberry


class GQLParams(ABC):
    pass


#     primary_key = None
#     description = None
#     summary = None
#     operation_id = None
#     tags = None


class GraphQLMixin:

    class gql_params(GQLParams):
        pass

    @classmethod
    def build_gql(cls):
        cls.gql = GraphQLFactory(cls)


class GraphQLFactory:

    def __init__(self, model):

        self.gql_type = self._generate_strawberry_type(model)
        self.gql_field = self._generate_strawberry_field(model)

    def _generate_strawberry_type(self, model) -> type:

        cols = [c for c in model.__table__.columns]

        vanilla_type = type(model.__name__, (object,), {})
        for c in cols:
            vanilla_type.__annotations__[c.name] = c.type.python_type

        return strawberry.type(vanilla_type)

    def _generate_strawberry_field(self, model) -> type:

        async def inner(self) -> self.gql_type:

            db = model.db_generator()
            objs = db.query(model).all()
            return [self.gql_type(obj) for obj in objs]

        inner.__name__ = model.__tablename__  # plural

        # sig = signature(inner)
        # sig = sig.replace(parameters=parameters)
        # f.__signature__ = sig

        return strawberry.field(inner)
