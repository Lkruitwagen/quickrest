import sys
from os.path import abspath, dirname

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

# append to sys path so pytest can find our example app
root_dir = dirname(dirname(abspath(__file__)))
sys.path.append(root_dir)

from example.app import Base, all_models  # noqa: E402
from example.app import app as example_app  # noqa: E402


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
def models():
    return all_models


@pytest.fixture(autouse=True)
def db():
    engine = create_engine("sqlite:///database.db", echo=False)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def app(db):
    return TestClient(example_app)


@pytest.fixture()
def setup_and_fill_db(db, admin_user_id, superuser_headers, app, resources):

    USERS = {resource["id"]: resource for resource in resources["owners"]}

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
