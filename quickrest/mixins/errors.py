from fastapi import HTTPException
from sqlalchemy.orm.exc import NoResultFound


def default_error_handler(e: Exception):
    if isinstance(e, NoResultFound):
        return HTTPException(status_code=404, detail="Resource not found")
    return HTTPException(status_code=500, detail="Internal server error")
