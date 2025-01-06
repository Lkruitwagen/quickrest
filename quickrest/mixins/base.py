from abc import ABC, abstractmethod
from typing import Callable, Optional
from uuid import UUID

from fastapi import Depends
from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings


class EnvSettings(BaseSettings):
    """
    Settings to load automatically from environment variables.

    Attributes:
        POSTGRES_DB_SCHEME (Optional[str]): The scheme for the Postgres database, defaults to just "postgresql".
        POSTGRES_DB_USER (Optional[str]): The username for the Postgres database.
        POSTGRES_DB_PASSWORD (Optional[str]): The password for the Postgres database.
        POSTGRES_DB_HOST (Optional[str]): The host for the Postgres database.
        POSTGRES_DB_PORT (Optional[int]): The port for the Postgres database.
        POSTGRES_DB_NAME (Optional[str]): The name of the Postgres database.
        SQLITE_DB_PATH (Optional[str]): A file path for the SQLite database (not pre-pended with `sqlite:///`).
        pg_dsn (Optional[PostgresDsn]): A postgres DSN generated from the environment variables.
        DB_CONNECTION_URL (Optional[str]): The connection string for the database, populated by the Postgres DSN or the SQLite path.
        QUICKREST_ID_TYPE (type): The default ID type for Resources, defaults to `Int`
        QUICKREST_USE_SLUG (bool): Whether to use slug unique identifiers on Resources, defaults to False
        QUICKREST_INDIRECT_SESSION_GENERATOR (str): The path to the session generator function, defaults to `quickrest.mixins.resource.default_sessionmaker`
        QUICKREST_INDIRECT_USER_GENERATOR (str): The path to the user generator function, defaults to `quickrest.mixins.resource.nullreturn`
        QUICKREST_ERROR_HANDLER (str): The path to the error handler function, defaults to `quickrest.mixins.errors.default_error_handler`

    """

    POSTGRES_DB_SCHEME: Optional[str] = None
    POSTGRES_DB_USER: Optional[str] = None
    POSTGRES_DB_PASSWORD: Optional[str] = None
    POSTGRES_DB_HOST: Optional[str] = None
    POSTGRES_DB_PORT: Optional[int] = None
    POSTGRES_DB_NAME: Optional[str] = None

    SQLITE_DB_PATH: Optional[str] = None

    pg_dsn: Optional[PostgresDsn] = None

    DB_CONNECTION_URL: Optional[str] = None

    # default ID type
    QUICKREST_ID_TYPE: type = int

    # default slug use
    QUICKREST_USE_SLUG: bool = False

    # session_generator
    QUICKREST_INDIRECT_SESSION_GENERATOR: str = (
        "quickrest.mixins.resource.default_sessionmaker"
    )

    # user_generator
    QUICKREST_INDIRECT_USER_GENERATOR: str = "quickrest.mixins.resource.nullreturn"

    # error handler
    QUICKREST_ERROR_HANDLER: str = "quickrest.mixins.errors.default_error_handler"

    @field_validator("pg_dsn", mode="after")
    @classmethod
    def set_pg_dsn(cls, v, info):
        if v is None:
            try:
                return PostgresDsn.build(
                    scheme=info.data["POSTGRES_DB_SCHEME"] or "postgresql",
                    username=info.data["POSTGRES_DB_USER"],
                    password=info.data["POSTGRES_DB_PASSWORD"],
                    host=info.data["POSTGRES_DB_HOST"],
                    port=info.data["POSTGRES_DB_PORT"],
                    path=info.data["POSTGRES_DB_NAME"],
                )
            except ValueError:
                return None
            except Exception as e:
                raise e
        return v

    @field_validator("DB_CONNECTION_URL", mode="after")
    def set_db_path(cls, v, info):
        if not v:
            if info.data.get("pg_dsn") is not None:
                return str(info.data["pg_dsn"])
            elif info.data.get("SQLITE_DB_PATH") is not None:
                return "sqlite:///" + info.data["SQLITE_DB_PATH"]
            else:
                return None
        return v

    @field_validator("QUICKREST_ID_TYPE", mode="before")
    def set_id_type(cls, v):
        if v:
            if isinstance(v, str):
                if v.lower() == "str":
                    return str
                elif v.lower() == "int":
                    return int
                elif v.lower() == "uuid":
                    return UUID
                else:
                    raise ValueError(
                        "ENV(QUICKREST_ID_TYPE) must be one of 'str', 'int', or 'uuid'"
                    )
            if v in (str, int, UUID):
                return v
            else:
                raise ValueError("ENV(QUICKREST_ID_TYPE) must be a string")
        return v


class BaseMixin:
    pass


class RESTFactory(ABC):

    METHOD: str
    CFG_NAME: str
    ROUTE: str
    controller: Callable

    @abstractmethod
    def controller_factory(self, model, **kwargs) -> Callable: ...  # noqa: E704

    def attach_route(self, model) -> None:

        model.router.add_api_route(
            self.ROUTE,
            self.controller,
            description=getattr(model, self.CFG_NAME).description,
            dependencies=[
                Depends(d) for d in getattr(model, self.CFG_NAME).dependencies
            ],
            summary=getattr(model, self.CFG_NAME).summary
            or self.METHOD.lower() + " " + model.__name__.lower(),
            tags=getattr(model, self.CFG_NAME).tags or [model.__name__],
            operation_id=getattr(model, self.CFG_NAME).operation_id,
            methods=[self.METHOD],
            status_code=getattr(self, "SUCCESS_CODE", None) or 200,
            response_model=getattr(self, "response_model", model.basemodel),
        )


env_settings = EnvSettings()
