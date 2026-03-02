from typing import Any, Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class ResponseEnvelope(BaseModel, Generic[T]):
    status: str  # "success" | "error"
    data: T | None = None
    message: str = ""


def success(data: Any = None, message: str = "OK") -> dict:
    return {"status": "success", "data": data, "message": message}


def error(message: str, data: Any = None) -> dict:
    return {"status": "error", "data": data, "message": message}
