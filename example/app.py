import logging

import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import ForeignKey, create_engine
from sqlalchemy.orm import Mapped, mapped_column, relationship, sessionmaker

from quickrest import (
    Base,
    CreateParams,
    Private,
    Publishable,
    ResourceParams,
    RouterFactory,
    User,
    build_resource,
)

# ### Auth stuff
# roll your own auth logic here
# ###


class UserToken(BaseModel):
    id: str
    permissions: list[str]


def get_current_user(request: Request):
    # write your own auth logic here - normally decoding tokens etc
    permissions = request.headers.get("permissions", "")
    _id = request.headers.get("id")
    permissions = permissions.split(",")
    return UserToken(
        id=_id,
        permissions=permissions,
    )


def check_user_is_userwriter(request: Request):
    # write your own auth logic here
    permissions = request.headers.get("permissions", "")
    permissions = permissions.split(",")
    if "write-user" in permissions:
        return True
    raise HTTPException(status_code=401, detail="Insufficient permissions")


def check_user_is_admin(request: Request):
    # write your own auth logic here
    permissions = request.headers.get("permissions", "")
    permissions = permissions.split(",")
    if "admin" in permissions:
        return True
    raise HTTPException(status_code=401, detail="Insufficient permissions")


# ### database boilerplate
# just normal sqlalchemy stuff!

engine = create_engine("sqlite:///database.db", echo=False)
SessionMaker = sessionmaker(bind=engine)

# ### Resource Definitions

# instantiate the Resource class
Resource = build_resource(
    user_generator=get_current_user,
    user_token_model=UserToken,
    sessionmaker=SessionMaker,
)


class Owner(
    Base,
    Resource,
    User,
):
    __tablename__ = "owners"
    first_name: Mapped[str] = mapped_column()
    last_name: Mapped[str] = mapped_column()

    # pets: Mapped[list["Pet"]] = relationship(back_populates="owner")

    certifications: Mapped[list["Certification"]] = relationship(
        secondary="owner_certifications",
    )

    class resource_cfg(ResourceParams):
        # choose which relationships should be accessible via URL /<resource>/<id>/<relationship>
        children = ["pets"]
        serialize = ["certifications"]

    class create_cfg(CreateParams):
        dependencies = [check_user_is_userwriter]


# models - just normal sqlalchemy models with the Resource mixin!
class Specie(
    Base,
    Resource,
):
    __tablename__ = "species"

    common_name: Mapped[str] = mapped_column()
    scientific_name: Mapped[str] = mapped_column()

    class create_cfg(CreateParams):
        dependencies = [check_user_is_admin]


class Pet(Base, Resource, Publishable(user_model=Owner)):
    __tablename__ = "pets"
    # note: all Resource classes have an id and slug column by default
    name: Mapped[str] = mapped_column()

    species_id: Mapped[int] = mapped_column(ForeignKey("species.id"))

    specie: Mapped["Specie"] = relationship()
    notes: Mapped[list["Note"]] = relationship()

    class resource_cfg(ResourceParams):
        # choose which relationships should be serialized on the reponse
        serialize = ["specie", "owner"]


class Note(Base, Resource, Private(user_model=Owner)):
    __tablename__ = "notes"

    text: Mapped[str] = mapped_column()
    pet_id: Mapped[int] = mapped_column(ForeignKey("pets.id"))


class Certification(
    Base,
    Resource,
):
    __tablename__ = "certifications"
    # note: all Resource classes have an id and slug column by default
    name: Mapped[str] = mapped_column()
    description: Mapped[str] = mapped_column()

    class create_cfg(CreateParams):
        dependencies = [check_user_is_admin]


class OwnerCertifications(Base):
    __tablename__ = "owner_certifications"
    owner_id: Mapped[int] = mapped_column(ForeignKey("owners.id"), primary_key=True)
    certification_id: Mapped[int] = mapped_column(
        ForeignKey("certifications.id"), primary_key=True
    )


all_models = {
    cls.__name__.lower(): cls for cls in [Owner, Pet, Specie, Note, Certification]
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
