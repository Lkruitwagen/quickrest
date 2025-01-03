import logging
import sys
from os.path import abspath, dirname
from uuid import UUID

import pytest
import yaml
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy import ForeignKey, create_engine
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import Mapped, mapped_column, relationship, sessionmaker

# append to sys path so pytest can find our example app
root_dir = dirname(dirname(abspath(__file__)))
sys.path.append(root_dir)


def user_headers(user_blob):
    return {
        "id": user_blob["id"],
        "permissions": ",".join(user_blob["permissions"]),
    }


@pytest.fixture(autouse=True)
def superuser_headers():
    return {
        "id": "superuser",
        "permissions": "write-user",
    }


@pytest.fixture(autouse=True)
def admin_user_id():
    return "dr_jan_itor"


@pytest.fixture(autouse=True)
def nonadmin_user_id():
    return "bonita_leashley"


@pytest.fixture(autouse=True)
def resources():
    resources_order = [
        # users first
        "owners",
        # then static and types
        "certifications",
        "species",
        # then user data
        "pets",
    ]

    resources = {
        resource: yaml.load(
            open(f"example/example_data/{resource}.yaml"), Loader=yaml.SafeLoader
        )
        for resource in resources_order
    }
    return resources


@pytest.fixture(autouse=True)
def USERS(resources):
    return {resource["id"]: resource for resource in resources["owners"]}


@pytest.fixture(autouse=True)
def PETS(resources):
    return {resource["id"]: resource for resource in resources["pets"]}


@pytest.fixture(autouse=True)
def db():

    from example.app import Base  # noqa: E402

    engine = create_engine("sqlite:///database.db", echo=False)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
    del Base


@pytest.fixture(autouse=True)
def app(db):
    from example.app import app as example_app

    return TestClient(example_app)


@pytest.fixture(autouse=True, scope="session")
def app_types():
    from quickrest import Base, ResourceParams, RouterFactory, build_mixin

    engine = create_engine("sqlite:///database-types.db", echo=False)

    SessionMaker = sessionmaker(bind=engine)

    # instantiate the Resource class
    ResourceInt = build_mixin(
        id_type=int,
        sessionmaker=SessionMaker,
    )

    ResourceUUID = build_mixin(
        id_type=UUID,
        sessionmaker=SessionMaker,
    )

    ResourceUUIDSlug = build_mixin(
        id_type=UUID,
        slug=True,
        sessionmaker=SessionMaker,
    )

    class Book(Base, ResourceInt):
        __tablename__ = "books"
        title: Mapped[str] = mapped_column()
        year: Mapped[int] = mapped_column()

        author_id: Mapped[int] = mapped_column(ForeignKey("authors.id"))
        author: Mapped["Author"] = relationship()

        author_last_name: AssociationProxy[str] = association_proxy(
            "author", "last_name"
        )

        class resource_cfg(ResourceParams):
            serialize = ["author_last_name"]

    class Author(Base, ResourceInt):
        __tablename__ = "authors"
        first_name: Mapped[str] = mapped_column()
        last_name: Mapped[str] = mapped_column()
        dark_secret: Mapped[str] = mapped_column()

        @property
        def full_name(self) -> str:
            return f"{self.first_name} {self.last_name}"

        class resource_cfg(ResourceParams):
            serialize = ["full_name"]
            pop_params = ["dark_secret"]

    class Cheese(Base, ResourceUUID):
        __tablename__ = "cheeses"
        name: Mapped[str] = mapped_column()
        origin: Mapped[str] = mapped_column()

    class Knight(Base, ResourceUUIDSlug):
        __tablename__ = "knights"
        name: Mapped[str] = mapped_column()
        is_round_table: Mapped[bool] = mapped_column()

    Base.metadata.create_all(engine)

    app = FastAPI(
        title="QuickRest Test integer id", separate_input_output_schemas=False
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        exc_str = f"{exc}".replace("\n", " ").replace("   ", " ")
        logging.error(f"{request}: {exc_str}")
        content = {"status_code": 10422, "message": exc_str, "data": None}
        return JSONResponse(
            content=content, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    RouterFactory.mount(
        app, {"authors": Author, "books": Book, "cheeses": Cheese, "knights": Knight}
    )

    yield TestClient(app)

    Base.metadata.drop_all(engine)


@pytest.fixture()
def setup_and_fill_db(db, admin_user_id, superuser_headers, app, resources, USERS):

    # post static and types
    for resource_name in ["certifications", "species"]:
        for resource in resources[resource_name]:
            r = app.post(
                f"/{resource_name}",
                json=resource,
                headers=user_headers(USERS[admin_user_id]),
            )
            r.raise_for_status()

    # post users
    for resource in USERS.values():
        r = app.post("/owners", json=resource, headers=superuser_headers)
        r.raise_for_status()

    # post data
    for resource_name in ["pets"]:
        for resource in resources[resource_name]:
            r = app.post(
                f"/{resource_name}",
                json=resource,
                headers=user_headers(USERS[resource["owner_id"]]),
            )
            r.raise_for_status()
