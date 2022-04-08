from pydantic import BaseModel as PBaseModel


def to_camel(string: str) -> str:
    splitted = string.split('_')
    return splitted[0] + ''.join(word.capitalize() for word in splitted[1:])


class BaseModel(PBaseModel):
    class Config:
        allow_population_by_field_name = True
        alias_generator = to_camel
