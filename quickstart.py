import uvicorn
from fastapi import FastAPI
from sqlalchemy import ForeignKey, create_engine
from sqlalchemy.orm import Mapped, mapped_column, relationship, sessionmaker

from losdos.gql_factory import GQLFactory
from losdos.mixins.resource import Base, Resource

# database boilerplate - just normal sqlalchemy stuff!
engine = create_engine("sqlite:///database.db", echo=True)
SessionMaker = sessionmaker(bind=engine)

# attach a sessionmaker to the ResourceBase class
ResourceMixin = Resource.with_sessionmaker(SessionMaker)


# models - just normal sqlalchemy models with the Resource mixin!
class Pet(Base, ResourceMixin):
    __tablename__ = "pets"
    # note: all Resource classes have an id and slug column by default
    name: Mapped[str] = mapped_column()
    species: Mapped[str] = mapped_column()
    owner_id: Mapped[int] = mapped_column(ForeignKey("owners.id"))

    owner: Mapped["Owner"] = relationship(
        back_populates="pets", cascade="all, delete-orphan"
    )


class Owner(Base, ResourceMixin):
    __tablename__ = "owners"
    first_name: Mapped[str] = mapped_column()
    last_name: Mapped[str] = mapped_column()

    pets: Mapped[list["Pet"]] = relationship(back_populates="owner")


all_models = {"pet": Pet, "owner": Owner}

# instantiate a FastAPI app
app = FastAPI(title="LosDos Quickstart", separate_input_output_schemas=False)

# # build create, read, update, delete routers for each resource and add them to the app
for resource in all_models.values():
    resource.build_router()
    app.include_router(resource.router)

# # build and add a GraphQL router
gql = GQLFactory(all_models.values())
app.add_route("/graphql", gql.router)

if __name__ == "__main__":
    Base.metadata.create_all(engine)
    uvicorn.run(app, host="0.0.0.0", port=8000)
