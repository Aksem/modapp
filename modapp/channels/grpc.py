from typing import AsyncIterator, Optional, Dict, Any, Type, TypeVar

from grpclib import client as grpclib_client
from grpclib.encoding.base import CodecBase
from grpclib.exceptions import GRPCError
from grpclib.const import Status as GrpcStatus

from modapp.base_converter import BaseConverter
from modapp.errors import BaseModappError, NotFoundError, InvalidArgumentError, ServerError
from modapp.client import BaseChannel
from modapp.models import BaseModel


T = TypeVar("T", bound=BaseModel)


# the same code as in grpc transport to made server & client independent
class RawCodec(CodecBase):
    __content_subtype__ = "proto"

    def encode(self, message, message_type):
        return message

    def decode(self, data: bytes, message_type):
        return data


class GrpcChannel(BaseChannel):
    def __init__(
        self, converter: BaseConverter, host: str = "127.0.0.1", port: int = 50051
    ) -> None:
        super().__init__(converter)

        self.__grpclib_channel: Optional[grpclib_client.Channel] = None
        self.__host = host
        self.__port = port

    def __establish_channel(self) -> grpclib_client.Channel:
        return grpclib_client.Channel(self.__host, self.__port, codec=RawCodec())

    def __aenter__(self):
        return self

    def __aexit__(self):
        if self.__grpclib_channel is not None:
            self.__grpclib_channel.close()
            self.__grpclib_channel = None

    async def send_unary_unary(
        self,
        route_path: str,
        request_data: BaseModel,
        reply_cls: Type[T],
        meta: Optional[Dict[str, Any]] = None,
    ) -> T:
        if self.__grpclib_channel is None:
            self.__grpclib_channel = self.__establish_channel()

        raw_data = self.converter.model_to_raw(request_data)
        # TODO: grpc errors to modapp errors
        method = grpclib_client.UnaryUnaryMethod(
            self.__grpclib_channel,
            route_path,
            None,
            None,
        )
        try:
            raw_reply = await method(raw_data)
        except GRPCError as grpc_error:
            raise self.__grpc_error_to_modapp(grpc_error)
        return self.converter.raw_to_model(raw_reply, reply_cls)

    async def send_unary_stream(
        self,
        route_path: str,
        request_data: BaseModel,
        reply_cls: Type[T],
        meta: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[T]:
        if self.__grpclib_channel is None:
            self.__grpclib_channel = self.__establish_channel()

        raw_data = self.converter.model_to_raw(request_data)
        method = grpclib_client.UnaryStreamMethod(
            self.__grpclib_channel,
            route_path,
            None,
            None,
        )
        try:
            async with method.open(timeout=0) as stream:
                await stream.send_message(raw_data, end=True)
                async for raw_message in stream:
                    yield self.converter.raw_to_model(raw_message, reply_cls)
        except GRPCError as grpc_error:
            raise self.__grpc_error_to_modapp(grpc_error)

    async def send_stream_unary(self):
        # TODO
        raise NotImplementedError()

    async def send_stream_stream(self):
        # TODO
        raise NotImplementedError()

    def __grpc_error_to_modapp(self, grpc_error: GRPCError) -> BaseModappError:
        print(1, grpc_error.status)
        if grpc_error.status == GrpcStatus.NOT_FOUND:
            print(2)
            return NotFoundError(grpc_error.message)
        elif grpc_error.status == GrpcStatus.INVALID_ARGUMENT:
            # TODO: add method in converter to convert proto to error obj payload
            return InvalidArgumentError({})
        else:
            return ServerError(grpc_error.message)
