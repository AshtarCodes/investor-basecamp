"""The structured error the worker returns instead of dying."""

from typing import Literal

from pricing_engine.models import Model
from pricing_engine.settlement import UnknownRootError

ErrorCode = Literal["invalid_json", "invalid_request", "unknown_type", "model_error", "internal"]


class WorkerError(Model):
    code: ErrorCode
    message: str


def error_of(error: Exception) -> WorkerError:
    """The structured error for an exception raised while pricing. Pure: the caller logs."""
    if isinstance(error, UnknownRootError):
        return WorkerError(code="model_error", message=str(error))
    return WorkerError(code="internal", message=f"{type(error).__name__}: {error}")
