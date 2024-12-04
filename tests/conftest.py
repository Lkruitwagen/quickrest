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


@pytest.fixture(autouse=True)
def resources():
    resources_order = [
        # static and types first
        "certifications",
        "species",
        # then users
        "owners",
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
def setup_and_fill_db(db, app, resources):
    for resource_name, resource_list in resources.items():
        for resource in resource_list:
            r = app.post(f"/{resource_name}", json=resource)
            r.raise_for_status()

    return True
