from __future__ import annotations

from typing import TYPE_CHECKING, Type

import orjson
from typing_extensions import override

from ..base_converter import BaseConverter
from ..base_model import BaseModel, ModelType
from ..errors import InvalidArgumentError, ServerError, NotFoundError

if TYPE_CHECKING:
    from ..errors import BaseModappError


class JsonConverter(BaseConverter):
    def __init__(self) -> None:
        super().__init__()

    @override
    def raw_to_model(self, raw: bytes, model_cls: Type[ModelType]) -> ModelType:
        return model_cls.validate_and_construct_from_dict(
            model_dict=(orjson.loads(raw) if len(raw) > 0 else {})
        )

    @override
    def model_to_raw(self, model: BaseModel) -> bytes:
        return orjson.dumps(model.to_dict())

    @override
    def error_to_raw(self, error: BaseModappError) -> bytes:
        if isinstance(error, InvalidArgumentError):
            error_details = error.errors_by_fields
        elif isinstance(error, NotFoundError):
            if len(error.args) > 0 and isinstance(error.args[0], str):
                error_details = error.args[0]
            else:
                error_details = "Not found"
        elif isinstance(error, ServerError):
            error_details = "Server error"
        else:
            error_details = "Internal error"
        return orjson.dumps({"error": error_details})
