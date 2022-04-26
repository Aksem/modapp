import json
from asyncio import iscoroutine
from loguru import logger
from pydantic import ValidationError

from .errors import InvalidArgumentError, ServerError
from .routing import Route


# TODO: output type
def deserialize_request(route: Route, data: bytes):
    proto_request = route.proto_request_type.FromString(data)
    request_dict = {
        field[0].name: field[1]
        for field in type(proto_request).ListFields(proto_request)
    }
    print(request_dict)
    # request_schema = route.request_type.schema()
    # protobuff ListFields method doesn't return empty string fields, but they are not neccessary
    # required
    # request_dict.update({
    #     field.name: ''
    #     for field in proto_request.DESCRIPTOR.fields
    #     if (field.name not in request_dict
    #         and request_schema['properties'][field.name].get('type', None) == 'string')
    # })
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
    return route.proto_reply_type(
        **json.loads(reply.json(by_alias=True))
    ).SerializeToString()
