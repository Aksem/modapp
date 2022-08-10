import orjson
from pydantic import BaseModel as PBaseModel, validator, ValidationError


def to_camel(string: str) -> str:
    splitted = string.split("_")
    return splitted[0] + "".join(word.capitalize() for word in splitted[1:])


def orjson_dumps(v, *, default):
    # orjson.dumps returns bytes, to match standard json.dumps we need to decode
    return orjson.dumps(v, default=default).decode()


class BaseModel(PBaseModel):
    class Config:
        allow_population_by_field_name = True
        alias_generator = to_camel
        # use orjson for better performance
        json_loads = orjson.loads
        json_dumps = orjson_dumps


__all__ = ["BaseModel", "validator", "to_camel", "ValidationError"]
