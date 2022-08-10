import orjson
from pydantic.types import (
    NoneStr,
    NoneBytes,
    StrBytes,
    NoneStrBytes,
    StrictStr,
    ConstrainedBytes,
    conbytes,
    ConstrainedList,
    conlist,
    ConstrainedSet,
    conset,
    ConstrainedFrozenSet,
    confrozenset,
    ConstrainedStr,
    constr,
    PyObject,
    ConstrainedInt,
    conint,
    PositiveInt,
    NegativeInt,
    NonNegativeInt,
    NonPositiveInt,
    ConstrainedFloat,
    confloat,
    PositiveFloat,
    NegativeFloat,
    NonNegativeFloat,
    NonPositiveFloat,
    ConstrainedDecimal,
    condecimal,
    UUID1,
    UUID3,
    UUID4,
    UUID5,
    FilePath,
    DirectoryPath,
    Json,
    JsonWrapper,
    SecretStr,
    SecretBytes,
    StrictBool,
    StrictBytes,
    StrictInt,
    StrictFloat,
    PaymentCardNumber,
    ByteSize,
    PastDate,
    FutureDate,
)
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


__all__ = [
    "BaseModel",
    "validator",
    "to_camel",
    "ValidationError",
    # pydantic types
    "NoneStr",
    "NoneBytes",
    "StrBytes",
    "NoneStrBytes",
    "StrictStr",
    "ConstrainedBytes",
    "conbytes",
    "ConstrainedList",
    "conlist",
    "ConstrainedSet",
    "conset",
    "ConstrainedFrozenSet",
    "confrozenset",
    "ConstrainedStr",
    "constr",
    "PyObject",
    "ConstrainedInt",
    "conint",
    "PositiveInt",
    "NegativeInt",
    "NonNegativeInt",
    "NonPositiveInt",
    "ConstrainedFloat",
    "confloat",
    "PositiveFloat",
    "NegativeFloat",
    "NonNegativeFloat",
    "NonPositiveFloat",
    "ConstrainedDecimal",
    "condecimal",
    "UUID1",
    "UUID3",
    "UUID4",
    "UUID5",
    "FilePath",
    "DirectoryPath",
    "Json",
    "JsonWrapper",
    "SecretStr",
    "SecretBytes",
    "StrictBool",
    "StrictBytes",
    "StrictInt",
    "StrictFloat",
    "PaymentCardNumber",
    "ByteSize",
    "PastDate",
    "FutureDate",
]
