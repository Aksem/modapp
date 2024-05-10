from __future__ import annotations
from typing import TYPE_CHECKING, Type
import orjson

from ..base_converter import BaseConverter
from ..base_model import BaseModel, ModelType

if TYPE_CHECKING:
    from ..errors import BaseModappError


class JsonConverter(BaseConverter):
    def raw_to_model(self, raw: bytes, model_cls: Type[ModelType]) -> ModelType:
        return model_cls(orjson.loads(raw))

    def model_to_raw(self, model: BaseModel) -> bytes:
        return orjson.dumps(model)

    def error_to_raw(self, error: BaseModappError) -> bytes:
        # TODO: define json message structure for error
        return orjson.dumps(error)
