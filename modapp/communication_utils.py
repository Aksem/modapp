import orjson
from datetime import timezone

from asyncio import iscoroutine
from loguru import logger
from pydantic import ValidationError
from google.protobuf.timestamp_pb2 import Timestamp

from .errors import InvalidArgumentError, ServerError
from .routing import Route
from .models import to_camel


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
    # protobuff ListFields method doesn't return boolean fields if they have value False
    request_dict.update(
        {
            field.name: False
            for field in proto_request.DESCRIPTOR.fields
            if (
                field.name not in request_dict
                and request_schema["properties"][field.name].get("type", None)
                == "boolean"
            )
        }
    )
    # print(data, request_dict, type(proto_request).ListFields(proto_request))
    print(request_dict)
    try:
        return route.request_type(**request_dict)
    except ValidationError as error:
        raise InvalidArgumentError(
            {str(error["loc"][0]): error["msg"] for error in error.errors()}
        )


async def run_request_handler(route, request_data):
    try:
        if iscoroutine(route.handler):
            reply = await route.handler(request_data)
        else:
            reply = route.handler(request_data)
        return reply
    except ValidationError as error:
        # failed to validate reply
        logger.critical(f"Failed to validate reply: {error}")
        raise ServerError()


# TODO: reply type
def serialize_reply(route: Route, reply) -> bytes:
    json_reply = orjson.loads(reply.json(by_alias=True))
    reply_schema = route.reply_type.schema()
    # convert datetime to google.protobuf.Timestamp instance
    # in pydantic model schema datetime has type 'string' and format 'date-time'
    json_reply.update(
        {
            to_camel(field): Timestamp(
                seconds=int(
                    reply.dict()[field].replace(tzinfo=timezone.utc).timestamp()
                )
                # TODO: nanos?
            )
            for field in reply.dict()
            if (
                reply_schema["properties"][to_camel(field)].get("format", None)
                == "date-time"
            )
        }
    )
    print(json_reply)
    return route.proto_reply_type(**json_reply).SerializeToString()
