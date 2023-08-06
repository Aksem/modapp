import re
from typing import TypeVar

from pydantic import BaseModel as PBaseModel
from pydantic import ValidationError, validator
from pydantic.networks import (
    AmqpDsn,
    AnyHttpUrl,
    AnyUrl,
    CockroachDsn,
    EmailStr,
    FileUrl,
    HttpUrl,
    IPvAnyAddress,
    IPvAnyInterface,
    IPvAnyNetwork,
    KafkaDsn,
    MongoDsn,
    NameEmail,
    PostgresDsn,
    RedisDsn,
)
from pydantic.types import (
    UUID1,
    UUID3,
    UUID4,
    UUID5,
    ByteSize,
    DirectoryPath,
    FilePath,
    FutureDate,
    Json,
    NegativeFloat,
    NegativeInt,
    NonNegativeFloat,
    NonNegativeInt,
    NonPositiveFloat,
    NonPositiveInt,
    PastDate,
    PositiveFloat,
    PositiveInt,
    SecretBytes,
    SecretStr,
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

# TODO: move
pattern = re.compile(r'(?<!^)(?=[A-Z])')
def to_snake(camelStr: str) -> str:
    return pattern.sub('_', camelStr).lower()


class BaseModel(PBaseModel):
    __modapp_path__: str = ''

    model_config = {
        'populate_by_name': True,
        'alias_generator': to_camel,
    }


ModelType = TypeVar("ModelType", bound=BaseModel)


__all__ = [
    "BaseModel",
    "ModelType",
    "validator",
    "to_camel",
    "ValidationError",
    # pydantic types
    "StrictStr",
    "conbytes",
    "conlist",
    "conset",
    "confrozenset",
    "constr",
    "conint",
    "PositiveInt",
    "NegativeInt",
    "NonNegativeInt",
    "NonPositiveInt",
    "confloat",
    "PositiveFloat",
    "NegativeFloat",
    "NonNegativeFloat",
    "NonPositiveFloat",
    "condecimal",
    "UUID1",
    "UUID3",
    "UUID4",
    "UUID5",
    "FilePath",
    "DirectoryPath",
    "Json",
    "SecretStr",
    "SecretBytes",
    "StrictBool",
    "StrictBytes",
    "StrictInt",
    "StrictFloat",
    "ByteSize",
    "PastDate",
    "FutureDate",
    # networks
    'AnyUrl',
    'AnyHttpUrl',
    'FileUrl',
    'HttpUrl',
    'EmailStr',
    'NameEmail',
    'IPvAnyAddress',
    'IPvAnyInterface',
    'IPvAnyNetwork',
    'PostgresDsn',
    'CockroachDsn',
    'AmqpDsn',
    'RedisDsn',
    'MongoDsn',
    'KafkaDsn',
]
