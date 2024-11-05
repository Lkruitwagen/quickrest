_¿REST API? ¿GraphQL? ¿Por qué no..._

# LosDos :v:

A schema-first FastAPI abstraction framework so your team can get developing FAST. 
Simply define your database schema and let LosDos generate all your pydantic objects, CRUD controllers and routers, and a GraphQL entrypoint.

[![License][license badge]][license]

[license badge]: https://img.shields.io/badge/License-MIT-blue.svg
[license]: https://opensource.org/licenses/MIT

## Quickstart

LosDos is available from the python package index: `pip install losdos`. 

LosDos exposes a `Resource` mixin that you can use with your SQLAlchemy ORM definitions. 
You can then use the LosDos `CRUDFactory` and `GraphQLFactory` to create CRUD (create, read, update, delete) REST routes for all resources, 
as well as a GraphQL entrypoint. 
Configuration classes can be used to inject `Dependencies` and other parameters into the resource-specific CRUD controllers and the GraphQL engine.

```python
from fastapi import FastAPI
from sqlalchemy import ForeignKey, create_engine
from sqlalchemy.orm import Mapped, mapped_column, relationship

from losdos import Resource, CRUDFactory, GraphQLFactory

# models - just normal sqlalchemy models with the Resource mixin!
class Pet(Resource):
    __tablename__ = "pets"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    species: Mapped[str] = mapped_column()
    owner_id: Mapped[int] = mapped_column(ForeignKey("owners.id"))

    owner: Mapped["Owner"] = relationship(
        back_populates="pets", cascade="all, delete-orphan"
    )

class Owner(Resource):
    __tablename__ = "owners"
    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column()
    last_name: Mapped[str] = mapped_column()

    pets: Mapped[list["Pet"]] = relationship(back_populates="owner")

all_models = {'pet': Pet, 'owner': Owner}

# instantiate a FastAPI app
app = FastAPI(title="LosDos Quickstart", separate_input_output_schemas=False)

# build create, read, update, delete routers for each resource and add them to the app
crud_routers = CRUDFactory(all_models)

for router in crud_routers:
    app.include_router(PetTable.router)

# build and add a GraphQL router
graphql_router = GraphQLFactory(all_models)
app.include_router(graphql_router)

if __name__ == "__main__":
    engine = create_engine("sqlite://", echo=True)
    Base.metadata.create_all(engine)
    app.run()
```

