import importlib
from uuid import UUID

from quickrest.mixins import base


def test_sqlite_case(monkeypatch):

    with monkeypatch.context() as monkeycontext:
        monkeycontext.setenv("SQLITE_DB_PATH", "database.db")

        importlib.reload(base)

        assert base.env_settings.SQLITE_DB_PATH == "database.db"
        assert base.env_settings.DB_PATH == "sqlite:///database.db"


def test_postgres_case(monkeypatch):

    with monkeypatch.context() as monkeycontext:
        monkeycontext.setenv("POSTGRES_DB_USER", "pguser")
        monkeycontext.setenv("POSTGRES_DB_PASSWORD", "pgdbpw")
        monkeycontext.setenv("POSTGRES_DB_HOST", "127.0.0.1")
        monkeycontext.setenv("POSTGRES_DB_PORT", "5432")
        monkeycontext.setenv("POSTGRES_DB_NAME", "mydb")

        importlib.reload(base)

        assert (
            str(base.env_settings.pg_dsn)
            == "postgresql://pguser:pgdbpw@127.0.0.1:5432/mydb"
        )
        assert (
            base.env_settings.DB_PATH
            == "postgresql://pguser:pgdbpw@127.0.0.1:5432/mydb"
        )


def test_postgres_case_fail(monkeypatch):

    with monkeypatch.context() as monkeycontext:
        monkeycontext.setenv("POSTGRES_DB_USER", "pguser")
        monkeycontext.setenv("POSTGRES_DB_PASSWORD", "pgdbpw")
        monkeycontext.setenv("POSTGRES_DB_PORT", "5432")
        monkeycontext.setenv("POSTGRES_DB_NAME", "mydb")

        importlib.reload(base)

        assert base.env_settings.pg_dsn is None
        assert base.env_settings.DB_PATH is None


def test_id_types(monkeypatch):
    with monkeypatch.context() as monkeycontext:
        monkeycontext.setenv("QUICKREST_ID_TYPE", "str")

        importlib.reload(base)

        assert base.env_settings.QUICKREST_ID_TYPE == str

    with monkeypatch.context() as monkeycontext:
        monkeycontext.setenv("QUICKREST_ID_TYPE", "int")

        importlib.reload(base)

        assert base.env_settings.QUICKREST_ID_TYPE == int

    with monkeypatch.context() as monkeycontext:
        monkeycontext.setenv("QUICKREST_ID_TYPE", "uuid")

        importlib.reload(base)

        assert base.env_settings.QUICKREST_ID_TYPE == UUID


def test_slug_bool(monkeypatch):
    with monkeypatch.context() as monkeycontext:
        monkeycontext.setenv("QUICKREST_USE_SLUG", "false")

        importlib.reload(base)

        assert base.env_settings.QUICKREST_USE_SLUG == False

    with monkeypatch.context() as monkeycontext:
        monkeycontext.setenv("QUICKREST_USE_SLUG", "true")

        importlib.reload(base)

        assert base.env_settings.QUICKREST_USE_SLUG == True
