import strawberry
from strawberry import Schema
from strawberry.asgi import GraphQL

from losdos.mixins.resource import Base


class GQLFactory:

    def __init__(self, models: list[Base]):

        self.Query = self.build_query(models)
        # self.mutations = self.build_mutation(models)

        self.schema = Schema(query=self.Query)
        self.router = GraphQL(self.schema)

    def build_query(self, model: list[Base]):
        Query = type(
            "Query", (object,), {m.__tablename__: m.gql.gql_field for m in model}
        )

        return strawberry.type(Query)
