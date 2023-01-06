import orjson
from pydantic import BaseModel as PBaseModel
from pydantic import ValidationError, validator
from pydantic.types import (
    UUID1,
    UUID3,
    UUID4,
    UUID5,
    ByteSize,
    ConstrainedBytes,
    ConstrainedDecimal,
    ConstrainedFloat,
    ConstrainedFrozenSet,
    ConstrainedInt,
    ConstrainedList,
    ConstrainedSet,
    ConstrainedStr,
    DirectoryPath,
    FilePath,
    FutureDate,
    Json,
    JsonWrapper,
    NegativeFloat,
    NegativeInt,
    NoneBytes,
    NoneStr,
    NoneStrBytes,
    NonNegativeFloat,
    NonNegativeInt,
    NonPositiveFloat,
    NonPositiveInt,
    PastDate,
    PaymentCardNumber,
    PositiveFloat,
    PositiveInt,
    PyObject,
    SecretBytes,
    SecretStr,
    StrBytes,
    StrictBool,
    StrictBytes,
    StrictFloat,
    StrictInt,
    StrictStr,
    conbytes,
    condecimal,
    confloat,
    confrozenset,
    conint,
    conlist,
    conset,
    constr,
)


def to_camel(string: str) -> str:
    splitted = string.split("_")
    return splitted[0] + "".join(word.capitalize() for word in splitted[1:])


def orjson_dumps(v, *, default) -> str:
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
