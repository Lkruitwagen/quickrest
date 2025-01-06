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

from quickrest import (
    Base,
    BaseUserModel,
    CreateConfig,
    ReadConfig,
    ResourceConfig,
    RouterFactory,
    SearchConfig,
    User,
    build_resource,
    make_private,
    make_publishable,
)

# ### Auth stuff
# roll your own auth logic here
# ###


class UserToken(BaseUserModel):
    id: str
    permissions: list[str]


async def get_current_user(request: Request) -> UserToken:
    # write your own auth logic here - normally decoding tokens etc
    permissions = request.headers.get("permissions", "")
    _id = request.headers.get("id")
    permissions = permissions.split(",")
    return UserToken(
        id=_id,
        permissions=permissions,
    )


async def check_user_is_userwriter(request: Request):
    # write your own auth logic here
    permissions = request.headers.get("permissions", "")
    permissions = permissions.split(",")
    if "write-user" in permissions:
        return True
    raise HTTPException(status_code=401, detail="Insufficient permissions")


async def check_user_is_admin(request: Request):
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


# load the similarity extension
@event.listens_for(engine, "connect")
def receive_connect(conn, _):
    conn.enable_load_extension(True)
    conn.load_extension(str(Path.cwd() / "tests" / "spellfix.so"))
    conn.enable_load_extension(False)


# ### Resource Definitions

# instantiate the Resource class
Resource = build_resource(
    id_type=str,
    user_generator=get_current_user,
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

    pets: Mapped[list["Pet"]] = relationship(back_populates="owner")

    certifications: Mapped[list["Certification"]] = relationship(
        secondary="owner_certifications",
    )

    class resource_cfg(ResourceConfig):
        serialize = ["certifications"]

    class create_cfg(CreateConfig):
        dependencies = [check_user_is_userwriter]

    class read_cfg(ReadConfig):
        # choose which relationships should be accessible via URL /<resource>/<id>/<relationship>
        routed_relationships = ["pets"]


# models - just normal sqlalchemy models with the Resource mixin!
class Specie(
    Base,
    Resource,
):
    __tablename__ = "species"

    common_name: Mapped[str] = mapped_column()
    scientific_name: Mapped[str] = mapped_column()

    class create_cfg(CreateConfig):
        dependencies = [check_user_is_admin]


class Pet(Base, Resource, make_publishable(user_model=Owner)):
    __tablename__ = "pets"
    # note: all Resource classes have an id and slug column by default
    name: Mapped[str] = mapped_column()
    vaccination_date: Mapped[Optional[date]] = mapped_column(nullable=True)

    species_id: Mapped[int] = mapped_column(ForeignKey("species.id"))

    specie: Mapped["Specie"] = relationship()
    notes: Mapped[list["Note"]] = relationship()

    class resource_cfg(ResourceConfig):
        # choose which relationships should be serialized on the reponse
        serialize = ["specie"]

    class search_cfg(SearchConfig):
        search_gte = ["vaccination_date"]  # greater than or equal to, list[str] | bool
        search_lt = ["vaccination_date"]  # less than, list[str] | bool
        search_similarity = ["name"]  # string trigram search
        search_similarity_threshold = 300  # trigram search threshold


class Note(Base, Resource, make_private(user_model=Owner)):
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

    class create_cfg(CreateConfig):
        dependencies = [check_user_is_admin]


class OwnerCertifications(Base):
    __tablename__ = "owner_certifications"
    owner_id: Mapped[int] = mapped_column(ForeignKey("owners.id"), primary_key=True)
    certification_id: Mapped[int] = mapped_column(
        ForeignKey("certifications.id"), primary_key=True
    )


# instantiate a FastAPI app
app = FastAPI(title="QuickRest Quickstart", separate_input_output_schemas=False)

# build create, read, update, delete routers for each resource and add them to the app
RouterFactory.mount(app, [Owner, Pet, Specie, Note, Certification])


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
