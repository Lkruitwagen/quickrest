import uvicorn
from fastapi import FastAPI
from sqlalchemy import ForeignKey, create_engine
from sqlalchemy.orm import Mapped, mapped_column, relationship, sessionmaker

from losdos.mixins.resource import Base, Resource
from losdos.router_factory import RouterFactory

# database boilerplate - just normal sqlalchemy stuff!
engine = create_engine("sqlite:///database.db", echo=True)
SessionMaker = sessionmaker(bind=engine)

# attach a sessionmaker to the ResourceBase class
ResourceMixin = Resource.with_sessionmaker(SessionMaker)


# models - just normal sqlalchemy models with the Resource mixin!
class Specie(Base, ResourceMixin):  # GLOBAL
    __tablename__ = "species"

    common_name: Mapped[str] = mapped_column()
    scientific_name: Mapped[str] = mapped_column()


class Pet(Base, ResourceMixin):  # Private
    __tablename__ = "pets"
    # note: all Resource classes have an id and slug column by default
    name: Mapped[str] = mapped_column()

    owner_id: Mapped[int] = mapped_column(ForeignKey("owners.id"))
    species_id: Mapped[int] = mapped_column(ForeignKey("species.id"))

    owner: Mapped["Owner"] = relationship(
        back_populates="pets",
    )
    specie: Mapped["Specie"] = relationship()

    class resource_cfg:
        # choose which relationships should be serialized on the reponse
        serialize = ["specie"]


class Owner(Base, ResourceMixin):  # User
    __tablename__ = "owners"
    first_name: Mapped[str] = mapped_column()
    last_name: Mapped[str] = mapped_column()

    pets: Mapped[list["Pet"]] = relationship(back_populates="owner")

    class resource_cfg:
        # choose which relationships should be accessible via URL /<resource>/<id>/<relationship>
        children = ["pets"]


all_models = {"pet": Pet, "specie": Specie, "owner": Owner}

# instantiate a FastAPI app
app = FastAPI(title="QuickRest Quickstart", separate_input_output_schemas=False)

# # build create, read, update, delete routers for each resource and add them to the app
RouterFactory.mount(app, all_models)

if __name__ == "__main__":
    Base.metadata.create_all(engine)
    uvicorn.run(app, host="0.0.0.0", port=8000)
