_You've been working really hard. You deserve a ..._

# QuickRest

A schema-first FastAPI abstraction framework so your team can put your feet up (or get back to the interesting stuff).
Simply define your database schema and let QuickRest generate all your pydantic objects, CRUD controllers and (nested) RESTful routes, complete with fine-grained access control.

[![License][license badge]][license]

![Coverage][coverage badge]

[license badge]: https://img.shields.io/badge/License-MIT-blue.svg
[license]: https://opensource.org/licenses/MIT


[coverage badge]: https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/Lkruitwagen/a16058370777530ed286dab325015195/raw/quickrest-coverage-badge.json


## Quickstart

QuickRest is available from the python package index: `pip install quickrest`.

QuickRest exposes a `Resource` mixin that you can use with your SQLAlchemy ORM definitions.
You can also mixin the access control pattern for each of your tables (which will be used to autogenerate routes).
Available patterns include a unique `User` table, a `Global` pattern, and `Private`, `Publishable`, and `Shareable` fine-grained access control patterns.
You can then use the QuickRest `RouteFactory` to create standard RESTful API routes based on the defined access-control patterns.

```python
import uvicorn
from fastapi import FastAPI
from sqlalchemy import ForeignKey, create_engine
from sqlalchemy.orm import Mapped, mapped_column, relationship, sessionmaker

from quickrest.mixins.resource import Base, Resource
from quickrest.router_factory import RouterFactory

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
        # which relationships should be accessible via URL /<resource>/<id>/<relationship>
        children = ["pets"]


all_models = {"pet": Pet, "specie": Specie, "owner": Owner}

# instantiate a FastAPI app
app = FastAPI(title="QuickRest Quickstart", separate_input_output_schemas=False)

# # build create, read, update, delete routers for each resource and add them to the app
RouterFactory.mount(app, all_models)

if __name__ == "__main__":
    Base.metadata.create_all(engine)
    uvicorn.run(app, host="0.0.0.0", port=8000)
```


# Access Control Pattern classes:

- **UserMixin**: Unique for the main User table. Can be `listable [bool | str]`. If `listable=column_name[str]`, users control their own listing permissions.
- **GlobalMixin**: No fine-grained access control. CRUD routes can still be protected with dependency injections (e.g. open access for `Read`, some 'admin' role for `Create,Update,Delete`)
- **PrivateMixin**: Only scoped to the owning `User` resource.
- **PublishableMixin**: Resources can be flagged as 'public', and then read by any user.
- **ShareableMixin**: Read-access can be given to a set of users apart from the owner.

# Generated Routes:

- All resources receive root `/<resource>{/<id>}` routes.
- Specified 'serialise' relationships will always be returned on the object
- 'children' resources relationships are mounted as  `/<resource>/<resource_id>/<child_resource>{/<child_resource_id>}` routes.
- 'children' resources are automatically nested: `/<resource>/<resource_id>/<child_resource>/<child_resource_id>/<nested_child_resource{/<nested_child_resource_id>}`
