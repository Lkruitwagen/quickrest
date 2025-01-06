from abc import ABC
from datetime import date, datetime
from functools import wraps
from inspect import Parameter, signature
from operator import gt, lt
from typing import Any, Callable, Optional, Union

from fastapi import Depends
from pydantic import BaseModel, Field, create_model
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, sessionmaker

from quickrest.mixins.base import BaseMixin, RESTFactory
from quickrest.mixins.utils import classproperty


class SearchConfig(ABC):
    """
    The `SearchConfig` class can optionally be defined on the resource class.
    The search route is used for searching for retrieving multiple resource objects
    and is exposed as a GET endpoint on the bare resource path `/{resource_name}`.
    This class should inherit from `SearchConfig` and must be called `search_cfg`.
    If `search_cfg` is set to `None`, then the search route isn't created.

    `SearchConfig` has router-defining attributes that can be set to configure the search route,
    including a description, summary, operation_id, and tag labels.
    The `dependencies` attribute can be set to a list of FastAPI dependencies that will be injected into the search route.

    `SearchConfig` also exposes powerful configuration options for filtering and searching for resources.
    The `search_eq` (equals), `search_gt` (greater-than), `search_gte` (greater-than-or-equal-to), `search_lt` (less-than),
    and `search_lte` (less-than-or-equal-to) attributes can be set to filter on numeric fields (int, float, date, datetime).
    These parameters can be provided with either a list of field names (`list[str]`) that will expose these fields in the search query,
    or a boolean value that will expose these fields in the search query for all numeric fields.

    For string fields, the `search_contains` attribute can be set to filter on string fields that contain a substring.
    The `search_similarity` attribute can be set to filter on string fields that are similar to a given string.
    As with numeric fields, these parameters can be set to either a list of field names (`list[str]`) or a boolean
    value that will expose all string fields in the search query.
    If both `search_contains` and `search_similarity` are set on a field, the response will include objects that match either condition.

    The `search_similarity_threshold` attribute can be set to specify the similarity threshold for the search.
    QuickRest supports both sqlite and postgresql databases for similarity search.
    For sqlite, the `editdist3` function is used to calculate the levenshtein distance between two strings, where string insertions and deletions incur a cost of 100,
    and string subsitituitons incur a cost of 150.
    The `search_similarity_threshold` should be set to the *maximum* distance allowed, and is given a default value of 300 if not set.
    The [Spellfix](https://www.sqlite.org/spellfix1.html) extension must be enabled in sqlite to use this feature.
    For postgresql, the `similarity` function is used to calculate the similarity between two strings, where a value of 1.0 indicates a perfect match.
    Similarity is calculated using the trigram index, which breaks strings into three-letter sequences and compares the sequences between two strings
    (a more powerful and versitile similarity measure than levenshtein distance).
    The `search_similarity_threshold` should be set to the *minimum* similarity allowed, and is given a default value of 0.7 if not set.
    The [pg_trgm](https://www.postgresql.org/docs/9.1/pgtrgm.html) extension must be enabled in postgresql to use this feature.

    Finally, the `results_limit` attribute can be set to specify the maximum number of results to return in a single search query, defaulting to 10.
    The route will also add a `page` parameter to the query, which can be used to paginate the results.

    See the example below for a demonstration of how to use the `SearchConfig` class.

    Attributes:
        description (str, optional): Description of the endpoint. Optional, defaults to `None`.
        summary (str, optional): Summary of the endpoint. Optional, defaults to `get {resource_name}`.
        operation_id (str, optional): Operation ID of the endpoint. Optional, defaults to `None`.
        tags (list[str], optional): Tags for the endpoint. Optional, defaults to `None`.
        dependencies (list[Callable]): Injectable callable dependencies for the endpoint. Optional, defaults to `[]`.
        required_params (list[str]): List of fields that are required in the search query. Optional, defaults to `[]`.
        pop_params (list[str]): List of fields that are excluded from the search query. Optional, defaults to `[]`.
        results_limit (int): Maximum number of results to return in a single search query. Optional, defaults to `10`.
        search_eq (Union[list[str], bool]): List of fields to filter on exact match, or boolean to apply to all numeric fields. Optional, defaults to `None`.
        search_gt (Union[list[str], bool]): List of fields to filter on greater than, or boolean to apply to all numeric fields. Optional, defaults to `None`.
        search_gte (Union[list[str], bool]): List of fields to filter on greater than or equal to, or boolean to apply to all numeric fields. Optional, defaults to `None`.
        search_lt (Union[list[str], bool]): List of fields to filter on less than, or boolean to apply to all numeric fields. Optional, defaults to `None`.
        search_lte (Union[list[str], bool]): List of fields to filter on less than or equal to, or boolean to apply to all numeric fields. Optional, defaults to `None`.
        search_contains (Union[list[str], bool]): List of fields to filter on contains, or boolean to apply to all string fields. Optional, defaults to `None`.
        search_similarity (Union[list[str], bool]): List of fields to filter on similarity, or boolean to apply to all string fields. Optional, defaults to `None`.
        search_similarity_threshold (Union[int, float]): Similarity threshold for the search. Optional, defaults to `300` for sqlite or `0.7` for postgres.
    """

    required_params: list[str] = []
    pop_params: list[str] = []

    results_limit: int = 10

    # for float, int, datetime:
    search_eq: Optional[Union[list[str], bool]] = None
    search_gt: Optional[Union[list[str], bool]] = None
    search_gte: Optional[Union[list[str], bool]] = None
    search_lt: Optional[Union[list[str], bool]] = None
    search_lte: Optional[Union[list[str], bool]] = None

    # for str:
    search_contains: Optional[Union[list[str], bool]] = None
    search_similarity: Optional[Union[list[str], bool]] = None
    search_similarity_threshold: Optional[Union[int, float]] = None

    # router method
    description: Optional[str] = None
    summary: Optional[str] = None
    operation_id: Optional[str] = None
    tags: Optional[list[str]] = None
    dependencies: list[Callable] = []


class SearchMixin(BaseMixin):
    """
    This mixin is automatically inherited by the `Resource` class and provides endpoints for searching for resources.
    The mixin also builds a Pydantic model for the input query of the search endpoint.

    ## SearchModel

    The `SearchModel` is a Pydantic model build using the fields of the sqlalchemy model.
    The model parameters are exposed as query parameters, so fastAPI automatically exposes them as query parameters on the route.
    The route is exposed directly on the resource root path `/{resource_name}` and accepts a GET method.
    The model may include a `slug` field if it has been specified on the Resource mixin, or the `id` field if it is a string.

    ## Example:

    This example shows a typical use case - filtering and searching for an 'employees' resource by business_group, name, start_date, and vaccation_days_taken.
    In this example, the `business_group` parameter is required, and the `secret_nickname` parameter is excluded from the search query.
    The construction of these query parameters is described above in the [`SearchConfig`]() class.

    Note that the `SearchEmployee` model isn't actually used as a request body schema, but fields are converted to url query parameters, e.g.

        GET /exmployees?business_group=HR&name=jessicaish&start_date_gte=2021-01-01&vaccation_days_taken_lt=10&limit=5

    === "SQLAlchemy Resource"

        ```python
        from sqlalchemy.orm import Mapped, mapped_column

        from quickrest import Base, Resource, SearchConfig

        from some_package.auth import admin_user


        class Employee(Base, Resource):
            __tablename__ = "employees"

            business_group: Mapped[str] = mapped_column()
            name: Mapped[str] = mapped_column()
            secret_nickname: Mapped[str] = mapped_column()
            start_date: Mapped[date] = mapped_column()
            vaccation_days_taken: Mapped[int] = mapped_column()

            class search_cfg(SearchConfig):
                # search filters
                search_gte = True  # applies to all numeric fields
                search_lt = True  # applies to all numeric fields
                search_contains = ["name"]
                search_similarity = ["name"]
                search_similarity_threshold = 500

                required_params = ["business_group"]  # require business_group in search
                pop_params = ["secret_nickname"]  # exclude secret_nickname from search

                # route params
                description = "search for employees"
                summary = "search for employees"
                operation_id = "search_employees"
                tags = ["employees"]
                dependencies = [admin_user]
        ```

    === "Generated query model"

        ```python
        from pydantic import BaseModel


        class SearchEmployee(BaseModel):

            # string fields
            business_group: str  # required, must be exact match
            name: Optional[str]  # not required, and can be used for contains or similarity

            # numeric fields
            start_date_gte: Optional[date]
            start_date_lt: Optional[date]
            vaccation_days_taken_gte: Optional[int]
            vaccation_days_taken_lt: Optional[int]

            # pagination fields
            limit: int = 10
            page: int = 0
        ```

    ## Endpoint - Search Resource

    The generated endpoint is a GET request to the resource root path `/{resource_name}`.

        GET /{resource_name}?{query_params}

    | Property | Description |
    | :--- | :---- |
    | Method | `GET` |
    | Route | `/{resource_name}` |
    | Request  | Path: `<none>` </br> Query: Resource SearchModel </br> Body: `<none>`|
    | Success Response | 200 OK: Resource [PaginatedBaseModel](resource.md#quickrest.mixins.resource.ResourceMixin._build_basemodel) |

    """

    _search = None

    class search_cfg(SearchConfig):
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

            if not isinstance(model._sessionmaker, sessionmaker):
                raise ValueError(
                    "Sessionmaker not set on model - search_similarity requires a database backend."
                )

            if model._sessionmaker.kw.get("bind").dialect.name == "sqlite":  # type: ignore

                self.similarity_fn = func.editdist3
                self.similarity_op = lt
                query_fields["threshold"] = (
                    int,
                    Field(title="threshold", default=300, gt=99),
                )

            elif model._sessionmaker.kw.get("bind").dialect.name == "postgresql":  # type: ignore
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

        return create_model("Paginate" + model.__name__, **fields)

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
