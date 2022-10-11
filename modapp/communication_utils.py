import orjson
from datetime import timezone
from typing import Dict, Any, List, Optional

from asyncio import iscoroutine
from loguru import logger
from pydantic import ValidationError
from google.protobuf.timestamp_pb2 import Timestamp

from .errors import InvalidArgumentError, ServerError
from .routing import Route
from .models import to_camel, BaseModel


# TODO: output type
def deserialize_request(route: Route, data: bytes):
    proto_request = route.proto_request_type.FromString(data)
    request_dict = {
        field[0].name: field[1]
        for field in type(proto_request).ListFields(proto_request)
    }
    request_schema = route.request_type.schema()
    # protobuff ListFields method doesn't return empty string fields, but they are not neccessary
    # required
    # request_dict.update({
    #     field.name: ''
    #     for field in proto_request.DESCRIPTOR.fields
    #     if (field.name not in request_dict
    #         and request_schema['properties'][field.name].get('type', None) == 'string')
    # })

    # protobuff ListFields method doesn't return boolean fields if they have value False)
    request_dict.update(
        {
            field.name: False
            for field in proto_request.DESCRIPTOR.fields
            if (
                field.name not in request_dict
                and field.name in request_schema["properties"]
                and request_schema["properties"][field.name].get("type", None)
                == "boolean"
            )
        }
    )

    # protobuff ListFields method doesn't return enum fields if they have value 0)
    fields_to_update: List[str] = []
    for field in proto_request.DESCRIPTOR.fields:
        if (
            field.name not in request_dict
            and field.name in request_schema["properties"]
            and request_schema["properties"][field.name].get("$ref", None) is not None
        ):
            definition_name = (
                request_schema["properties"][field.name].get("$ref", "").split("/")[-1]
            )
            try:
                # can ref be imported? TODO: check
                definition = request_schema["definitions"][definition_name]
            except KeyError:
                logger.warning(
                    f"Field '{field.name}' has reference to definition, but definition was not found"
                )
                continue

            if definition["type"] == "integer" and "enum" in definition:
                fields_to_update.append(field.name)
    request_dict.update({field: 0 for field in fields_to_update})

    # request is not neccessary valid utf-8 string, handle errors
    logger.trace(str(request_dict).encode("utf-8", errors="replace"))
    try:
        return route.request_type(**request_dict)
    except ValidationError as error:
        raise InvalidArgumentError(
            {str(error["loc"][0]): error["msg"] for error in error.errors()}
        )


async def run_request_handler(route, handler_arguments: Dict[str, Any]) -> BaseModel:
    try:
        if iscoroutine(route.handler):
            reply = await route.handler(**handler_arguments)
        else:
            reply = route.handler(**handler_arguments)
        return reply
    except ValidationError as error:
        # failed to validate reply
        logger.critical(f"Failed to validate reply: {error}")
        raise ServerError()


# TODO: reply type
def serialize_reply(route: Route, reply: Optional[BaseModel]) -> bytes:
    if reply is None:
        logger.error(f"Route handler '{route.path}' doesn't return value")
        raise ServerError("Internal error")

    json_reply = orjson.loads(reply.json(by_alias=True))

    def fix_json(model, json):
        model_schema = type(model).schema()
        for field in model.__dict__:
            # convert datetime to google.protobuf.Timestamp instance
            # in pydantic model schema datetime has type 'string' and format 'date-time'
            if (
                model_schema["properties"][to_camel(field)].get("format", None)
                == "date-time"
            ):
                json[to_camel(field)] = Timestamp(
                    seconds=int(
                        model.__dict__[field].replace(tzinfo=timezone.utc).timestamp()
                    )
                    # TODO: nanos?
                )
            elif "$ref" in model_schema["properties"][to_camel(field)]:
                # model reference, fix recursively
                fix_json(model.__dict__[field], json[to_camel(field)])

    fix_json(reply, json_reply)
    # print(json_reply)
    return route.proto_reply_type(**json_reply).SerializeToString()
