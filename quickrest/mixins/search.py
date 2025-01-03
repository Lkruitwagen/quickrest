from abc import ABC
from datetime import date, datetime
from functools import wraps
from inspect import Parameter, signature
from operator import gt, lt
from typing import Any, Callable, Optional, Union

from fastapi import Depends
from pydantic import BaseModel, Field, create_model
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from quickrest.mixins.base import BaseMixin, RESTFactory
from quickrest.mixins.utils import classproperty


class SearchParams(ABC):
    required_params: list[str] = []
    pop_params: Optional[list[str]] = None

    results_limit: int = 10

    # for float, int, datetime:
    search_eq: Optional[Union[list[str], bool]] = None  # is precisely equal to
    search_gt: Optional[Union[list[str], bool]] = None  # greater than, list[str] | bool
    search_gte: Optional[Union[list[str], bool]] = (
        None  # greater than or equal to, list[str] | bool
    )
    search_lt: Optional[Union[list[str], bool]] = None  # less than, list[str] | bool
    search_lte: Optional[Union[list[str], bool]] = (
        None  # less than or equal to, list[str] | bool
    )

    # for str:
    search_contains: Optional[Union[list[str], bool]] = None  # string contains search
    search_similarity: Optional[Union[list[str], bool]] = None  # string trigram search
    search_similarity_threshold: Optional[Union[int, float]] = None

    # router method
    description: Optional[str] = None
    summary: Optional[str] = None
    operation_id: Optional[str] = None
    tags: Optional[list[str]] = None
    dependencies: list[Callable] = []


class SearchMixin(BaseMixin):

    _search = None

    class search_cfg(SearchParams):
        pass

    @classproperty
    def search(cls):

        if cls._search is None:
            cls._search = SearchFactory(cls)
        return cls._search


class BaseModelWithBridge(BaseModel):
    _bridge: Callable


class SearchFactory(RESTFactory):

    METHOD = "GET"
    CFG_NAME = "search_cfg"
    ROUTE = ""

    def __init__(self, model):
        self.input_model = self._generate_input_model(model)
        self.response_model = self._generate_response_model(model)
        self.controller = self.controller_factory(model)

    def _generate_input_model(self, model) -> type[BaseModelWithBridge]:

        def maybe_add_param(search_cfg, name):
            add_param_fields = []

            # equals param
            if isinstance(search_cfg.search_eq, bool):
                if search_cfg.search_eq:
                    add_param_fields.append(name + "_eq")
            elif isinstance(search_cfg.search_eq, list):
                if name in search_cfg.search_eq:
                    add_param_fields.append(name + "_eq")

            # greater than param
            if isinstance(search_cfg.search_gt, bool):
                if search_cfg.search_gt:
                    add_param_fields.append(name + "_gt")
            elif isinstance(search_cfg.search_gt, list):
                if name in search_cfg.search_gt:
                    add_param_fields.append(name + "_gt")

            # greater than or equal param
            if isinstance(search_cfg.search_gte, bool):
                if search_cfg.search_gte:
                    add_param_fields.append(name + "_gte")
            elif isinstance(search_cfg.search_gte, list):
                if name in search_cfg.search_gte:
                    add_param_fields.append(name + "_gte")

            # less than param
            if isinstance(search_cfg.search_lt, bool):
                if search_cfg.search_lt:
                    add_param_fields.append(name + "_lt")
            elif isinstance(search_cfg.search_lt, list):
                if name in search_cfg.search_lt:
                    add_param_fields.append(name + "_lt")

            # less than or equal param
            if isinstance(search_cfg.search_lte, bool):
                if search_cfg.search_lte:
                    add_param_fields.append(name + "_lte")
            elif isinstance(search_cfg.search_lte, list):
                if name in search_cfg.search_lte:
                    add_param_fields.append(name + "_lte")

            return add_param_fields

        cols = [c for c in model.__table__.columns]

        # build the query fields
        query_fields: Any = {}

        for c in cols:
            if c.name not in ["id"]:

                if c.type.python_type in [float, int, date, datetime]:
                    # handle filtering on numeric data
                    add_fields = maybe_add_param(model.search_cfg, c.name)

                    for new_field in add_fields:
                        if c.name in model.search_cfg.required_params:
                            query_fields[new_field] = (
                                c.type.python_type,
                                Field(title=new_field, default=...),
                            )
                        else:
                            query_fields[new_field] = (
                                Optional[c.type.python_type],
                                Field(title=new_field, default=None),
                            )

                elif c.type.python_type == str:
                    # add filtering for string data
                    if c.name in model.search_cfg.required_params:
                        query_fields[c.name] = (str, Field(title=c.name, default=...))
                    else:
                        query_fields[c.name] = (
                            Optional[str],
                            Field(title=c.name, default=None),
                        )

                elif c.type.python_type == bool:
                    # add filtering for boolean data
                    if c.name in model.search_cfg.required_params:
                        query_fields[c.name] = (bool, Field(title=c.name, default=...))
                    else:
                        query_fields[c.name] = (
                            Optional[bool],
                            Field(title=c.name, default=None),
                        )

                else:
                    print("unknown", c.name, c.type.python_type)
                    print(repr(c.type.python_type))

        # add pagination
        query_fields["limit"] = (
            int,
            Field(title="limit", default=model.search_cfg.results_limit),
        )
        query_fields["page"] = (int, Field(title="page", default=0))

        # maybe add similarity threshold
        if model.search_cfg.search_similarity is not None:

            if model._sessionmaker.kw.get("bind").dialect.name == "sqlite":

                self.similarity_fn = func.editdist3
                self.similarity_op = lt
                query_fields["threshold"] = (
                    int,
                    Field(title="threshold", default=300, gt=99),
                )

            elif model._sessionmaker.kw.get("bind").dialect.name == "postgresql":
                self.similarity_fn = func.similarity
                self.similarity_op = gt
                query_fields["threshold"] = (
                    float,
                    Field(title="threshold", default=0.7, lt=1.0),
                )

            else:
                raise ValueError(
                    "Unsupported database: {}".format(
                        model._sessionmaker.kw.get("bind")
                    )
                )

        query_model = create_model(
            "Search" + model.__name__,
            __base__=BaseModelWithBridge,
            **query_fields,
        )

        bridge_parameters = [
            Parameter(
                name,
                Parameter.POSITIONAL_OR_KEYWORD,
                default=field.default,
                annotation=type_annotation,
            )
            for name, (type_annotation, field) in query_fields.items()
        ]

        def bridge_inner(*args, **kwargs) -> model:
            return query_model(**kwargs)

        @wraps(bridge_inner)
        def bridge(*args, **kwargs):
            return bridge_inner(*args, **kwargs)

        # Override signature
        sig = signature(bridge_inner)
        sig = sig.replace(parameters=bridge_parameters)
        bridge.__signature__ = sig  # type: ignore

        query_model._bridge = bridge

        return query_model

    def _generate_response_model(self, model) -> BaseModel:

        [c for c in model.__table__.columns]

        fields: Any = {
            "page": (int, Field(title="page")),
            "total_pages": (int, Field(title="total_pages")),
            model.__tablename__: (
                list[model.basemodel],
                Field(title=model.__tablename__),
            ),
        }

        return create_model("SearchResponse" + model.__name__, **fields)

    def controller_factory(self, model):

        parameters = [
            Parameter(
                "query",
                Parameter.POSITIONAL_OR_KEYWORD,
                default=Depends(self.input_model._bridge),
                annotation=self.input_model,
            ),
            Parameter(
                "db",
                Parameter.POSITIONAL_OR_KEYWORD,
                default=Depends(model.db_generator),
                annotation=Session,
            ),
            Parameter(
                "user",
                Parameter.POSITIONAL_OR_KEYWORD,
                default=Depends(model._user_generator),
                annotation=model._user_generator.__annotations__["return"],
            ),
        ]

        async def inner(*args, **kwargs) -> list[model]:
            db = kwargs["db"]
            query = kwargs["query"]
            user = kwargs["user"]

            try:

                Q = db.query(model)

                # add access control
                if hasattr(model, "access_control"):
                    Q = model.access_control(Q, user)

                for name, val in query.model_dump().items():
                    if val is not None:

                        # check type of param

                        if type(val) is bool:
                            Q = Q.filter(getattr(model, name) == val)

                        if type(val) in [int, float, date, datetime]:

                            compare_type = name.split("_")[-1]
                            param_name = "_".join(name.split("_")[:-1])

                            if compare_type == "eq":
                                Q = Q.filter(getattr(model, param_name) == val)
                            elif compare_type == "gte":
                                Q = Q.filter(getattr(model, param_name) >= val)
                            elif compare_type == "gt":
                                Q = Q.filter(getattr(model, param_name) > val)
                            elif compare_type == "lte":
                                Q = Q.filter(getattr(model, param_name) <= val)
                            elif compare_type == "lt":
                                Q = Q.filter(getattr(model, param_name) < val)

                        if type(val) is str:

                            if (
                                model.search_cfg.search_contains
                                and model.search_cfg.search_similarity
                            ):
                                # if contains AND similarity
                                Q = Q.filter(
                                    or_(
                                        getattr(model, name).contains(val),
                                        self.similarity_op(
                                            self.similarity_fn(
                                                getattr(model, name), val
                                            ),
                                            query.threshold,
                                        ),
                                    )
                                )

                            elif model.search_cfg.search_contains:
                                # if just contains
                                Q = Q.filter(getattr(model, name).contains(val))

                            elif model.search_cfg.search_similarity:
                                # if just similarity
                                Q = Q.filter(
                                    self.similarity_op(
                                        self.similarity_fn(getattr(model, name), val),
                                        query.threshold,
                                    )
                                )

                            else:
                                # else jsut extact match
                                Q = Q.filter(getattr(model, name) == val)

                # pagination
                # Count total results (without fetching)
                total_results = (
                    db.query(func.count()).select_from(Q.subquery()).scalar()
                )

                # Get filtered set of results
                filtered_results = (
                    Q.offset(query.page * query.limit).limit(query.limit).all()
                )

                pydnatic_results = [
                    model.basemodel.model_validate(obj, from_attributes=True)
                    for obj in filtered_results
                ]

                return self.response_model(
                    **{
                        "page": query.page,
                        "total_pages": (total_results // query.limit) + 1,
                        model.__tablename__: pydnatic_results,
                    }
                )
            except Exception as e:
                raise model._error_handler(e)

        @wraps(inner)
        async def f(*args, **kwargs):
            return await inner(*args, **kwargs)

        # Override signature
        sig = signature(inner)
        sig = sig.replace(parameters=parameters)
        f.__signature__ = sig

        return f
