# QuickRest

A schema-first CRUD-generation framework for FastAPI and SQLAlchemy so your team can put your feet up (or get back to the interesting stuff).

[![License][license badge]][license]
![Coverage][coverage badge]

[license badge]: https://img.shields.io/badge/License-MIT-blue.svg
[license]: https://opensource.org/licenses/MIT


[coverage badge]: https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/Lkruitwagen/a16058370777530ed286dab325015195/raw/quickrest_coverage_badge.json


Full Documentation: [lucaskruitwagen.github.io/quickrest](https://lkruitwagen.github.io/quickrest/)

Issues and Feature Requests: [github.com/Lkruitwagen/quickrest/issues](https://github.com/Lkruitwagen/quickrest/issues)

## Features

- Mixins classes for [SQLAlchemy](https://www.sqlalchemy.org/) declarative ORM classes that automatically build `create`, `read`, `update`, `delete`, and `search` (CRUD+Search) [FastAPI](https://fastapi.tiangolo.com/) endpoints and [Pydantic](https://docs.pydantic.dev/latest/) models.
- Full exposure of joined tables, either via serialized related objects or additional `GET <resource>/<id>/<relationship>` routes
- Route-level protections via standard dependency injection
- Row-level fine-grained access control via developer-defineable user generation
- Many additional configuration options available via `<Method>Config` classes

See [docs](https://lkruitwagen.github.io/quickrest/) for more.


## Installation

QuickRest is available from the python package index: `pip install fastapi-quickrest`.

## Quickstart

Simple mixin the `Resource` class with your ORM classes and you're good to go.
Define some environment variables to set the default sessionmaker and user generator for the `Resource` class ()or use the `build_resource` method.
Mixin the `User`, `Private (via make_private)`, and `Publishable (via make_publishabe)` classes to add fine-grained access control.

Check the docs for the full range of customisation options.

```python
from datetime import date
from typing import Optional

import uvicorn
from fastapi import FastAPI
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quickrest import (
    Base,
    ReadConfig,
    ResourceConfig,
    RouterFactory,
    SearchConfig,
    Resource,
)


class Owner(
    Base,
    Resource,
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

    class read_cfg(ReadConfig):
        # choose which relationships should be accessible via URL /<resource>/<id>/<relationship>
        routed_relationships = ["pets"]


class Specie(
    Base,
    Resource,
):
    __tablename__ = "species"

    common_name: Mapped[str] = mapped_column()
    scientific_name: Mapped[str] = mapped_column()


class Pet(Base, Resource):
    __tablename__ = "pets"
    # note: all Resource classes have an id and slug column by default
    name: Mapped[str] = mapped_column()
    vaccination_date: Mapped[Optional[date]] = mapped_column(nullable=True)

    species_id: Mapped[int] = mapped_column(ForeignKey("species.id"))
    owner_id: Mapped[int] = mapped_column(ForeignKey("owners.id"))

    owner: Mapped["Owner"] = relationship()
    specie: Mapped["Specie"] = relationship()
    notes: Mapped[list["Note"]] = relationship()

    class resource_cfg(ResourceConfig):
        # choose which relationships should be serialized on the reponse
        serialize = ["specie"]

    class search_cfg(SearchConfig):
        search_gte = ["vaccination_date"]  # greater than or equal to, list[str] | bool
        search_lt = ["vaccination_date"]  # less than, list[str] | bool


class Note(Base, Resource):
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

if __name__ == "__main__":
    # Base.metadata.create_all(Resource._sessionmaker.kw.get("bind"))  # uncomment this line to create the tables in db backend
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Contributing

Contributions welcome!

To set up for development simply clone the repo and then:

    pip install -e .[dev]
