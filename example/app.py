import logging

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import ForeignKey, create_engine
from sqlalchemy.orm import Mapped, mapped_column, relationship, sessionmaker

from quickrest.mixins.resource import Base, Resource, ResourceParams
from quickrest.router_factory import RouterFactory

# database boilerplate - just normal sqlalchemy stuff!
engine = create_engine("sqlite:///database.db", echo=False)
SessionMaker = sessionmaker(bind=engine)


class Owner(Base, Resource.from_factory(sessionmaker=SessionMaker)):  # , User):  # User
    __tablename__ = "owners"
    first_name: Mapped[str] = mapped_column()
    last_name: Mapped[str] = mapped_column()

    pets: Mapped[list["Pet"]] = relationship(back_populates="owner")

    certifications: Mapped[list["Certification"]] = relationship(
        secondary="owner_certifications",
    )

    class resource_cfg(ResourceParams):
        # choose which relationships should be accessible via URL /<resource>/<id>/<relationship>
        children = ["pets"]
        serialize = ["certifications"]


# models - just normal sqlalchemy models with the Resource mixin!
class Specie(Base, Resource.from_factory(sessionmaker=SessionMaker)):  # GLOBAL
    __tablename__ = "species"

    common_name: Mapped[str] = mapped_column()
    scientific_name: Mapped[str] = mapped_column()


class Pet(
    Base, Resource.from_factory(sessionmaker=SessionMaker)
):  # , Publishable(Owner)):  # Publishable
    __tablename__ = "pets"
    # note: all Resource classes have an id and slug column by default
    name: Mapped[str] = mapped_column()

    owner_id: Mapped[int] = mapped_column(ForeignKey("owners.id"))
    species_id: Mapped[int] = mapped_column(ForeignKey("species.id"))

    owner: Mapped["Owner"] = relationship(
        back_populates="pets",
    )
    specie: Mapped["Specie"] = relationship()

    class resource_cfg(ResourceParams):
        # choose which relationships should be serialized on the reponse
        serialize = ["specie"]


class Certification(
    Base, Resource.from_factory(sessionmaker=SessionMaker)
):  # , Private(Owner)):  # Private, many-to-many
    __tablename__ = "certifications"
    # note: all Resource classes have an id and slug column by default
    name: Mapped[str] = mapped_column()
    description: Mapped[str] = mapped_column()


class OwnerCertifications(Base):
    __tablename__ = "owner_certifications"
    owner_id: Mapped[int] = mapped_column(ForeignKey("owners.id"), primary_key=True)
    certification_id: Mapped[int] = mapped_column(
        ForeignKey("certifications.id"), primary_key=True
    )


all_models = {
    "pet": Pet,
    "specie": Specie,
    "owner": Owner,
    "certification": Certification,
}

# instantiate a FastAPI app
app = FastAPI(title="QuickRest Quickstart", separate_input_output_schemas=False)

# build create, read, update, delete routers for each resource and add them to the app
RouterFactory.mount(app, all_models)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    exc_str = f"{exc}".replace("\n", " ").replace("   ", " ")
    logging.error(f"{request}: {exc_str}")
    content = {"status_code": 10422, "message": exc_str, "data": None}
    return JSONResponse(
        content=content, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
    )


if __name__ == "__main__":
    Base.metadata.create_all(engine)
    uvicorn.run(app, host="0.0.0.0", port=8000)
