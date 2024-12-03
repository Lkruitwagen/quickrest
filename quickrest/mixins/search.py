from abc import ABC
from datetime import date, datetime
from functools import wraps
from inspect import Parameter, signature
from typing import Optional

from fastapi import Depends
from pydantic import BaseModel, Field, create_model
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from losdos.mixins.base import BaseMixin, RESTFactory


class SearchParams(ABC):
    required_params = []
    pop_params = None

    results_limit = None

    # for float, int, datetime:
    search_eq = None  # is precisely equal to
    search_gt = None  # greater than, list[str] | bool
    search_gte = None  # greater than or equal to, list[str] | bool
    search_lt = None  # less than, list[str] | bool
    search_lte = None  # less than or equal to, list[str] | bool

    # for str:
    search_contains = None  # string contains search
    search_trgm = None  # string trigram search
    search_trgm_threshold = None

    # router method
    description = None
    summary = None
    operation_id = None
    tags = None


class SearchMixin(BaseMixin):

    class search_cfg(SearchParams):
        pass

    @classmethod
    def build_search(cls):
        cls.search = SearchFactory(cls)


class SearchFactory(RESTFactory):

    METHOD = "GET"
    CFG_NAME = "search_cfg"
    ROUTE = ""

    def __init__(self, model):
        self.input_model = self._generate_input_model(model)
        self.response_model = self._generate_response_model(model)
        self.controller = self.controller_factory(model)
        self.attach_route(model)

    def _generate_input_model(self, model) -> BaseModel:

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
        query_fields = {}
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

                else:
                    print("unknown", c.name, c.type.python_type)
                    print(repr(c.type.python_type))

        # add pagination
        query_fields["limit"] = (
            int,
            Field(title="limit", default=model.search_cfg.results_limit),
        )
        query_fields["page"] = (int, Field(title="page", default=0))

        # maybe add trgm threshold
        if model.search_cfg.search_trgm is not None:
            query_fields["threshold"] = (float, Field(title="threshold", default=0.7))

        query_model = create_model(
            model.__name__,
            __base__=BaseModel,
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
        bridge.__signature__ = sig

        query_model.bridge = bridge

        return query_model

    def _generate_response_model(self, model) -> BaseModel:
        cols = [c for c in model.__table__.columns]
        return create_model(
            model.__name__, **{c.name: (c.type.python_type, ...) for c in cols}
        )

    def controller_factory(self, model):

        parameters = [
            Parameter(
                "query",
                Parameter.POSITIONAL_OR_KEYWORD,
                default=Depends(self.input_model.bridge),
                annotation=self.input_model,
            ),
            Parameter(
                "db",
                Parameter.POSITIONAL_OR_KEYWORD,
                default=Depends(model.db_generator),
                annotation=Session,
            ),
        ]

        def inner(*args, **kwargs) -> list[model]:
            db = kwargs.get("db")
            query = kwargs.get("query")

            Q = db.query(model)

            for name, val in query.model_dump().items():
                if val is not None:

                    # check type of param

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
                            and model.search_cfg.search_trgm
                        ):
                            # if contains AND trgm
                            Q = Q.filter(
                                or_(
                                    getattr(model, name).contains(val),
                                    func.similarity(getattr(model, name), val)
                                    > query.threshold,
                                )
                            )

                        elif model.search_cfg.search_contains:
                            # if just contains
                            Q = Q.filter(getattr(model, name).contains(val))

                        elif model.search_cfg.search_trgm:
                            # if just trgm
                            Q = Q.filter(
                                func.similarity(getattr(model, name), val)
                                > query.threshold
                            )

                        else:
                            # else jsut extact match
                            Q = Q.filter(getattr(model, name) == val)

            # pagination
            # Count total results (without fetching)
            db.query(func.count()).select_from(Q.subquery()).scalar()

            # Get filtered set of results
            filtered_results = (
                Q.offset(query.page * query.limit).limit(query.limit).all()
            )

            return filtered_results

        @wraps(inner)
        def f(*args, **kwargs):
            return inner(*args, **kwargs)

        # Override signature
        sig = signature(inner)
        sig = sig.replace(parameters=parameters)
        f.__signature__ = sig

        return f
