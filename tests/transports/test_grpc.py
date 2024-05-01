import asyncio
import importlib
import multiprocessing
import os
import sys
import time
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator
from pathlib import Path
import socket
from contextlib import closing

import grpc_tools.protoc
from grpclib.client import Channel
from google.protobuf import message as protobuf_message
from loguru import logger

from modapp.models import BaseModel
from modapp.routing import APIRouter, Cardinality, RouteMeta
from modapp.validators.pydantic import PydanticValidator
from modapp.converters.protobuf import ProtobufConverter
from modapp.transports.grpc import (
    GrpcTransport,
    GrpcTransportConfig,
)
from modapp.server import Modapp


@asynccontextmanager
async def grpc_modapp_server_with_router(
    router: APIRouter, protos: dict[str, type[protobuf_message.Message]], port: int
) -> AsyncGenerator[Modapp, None]:
    converter = ProtobufConverter(protos=protos, validator=PydanticValidator())
    config = GrpcTransportConfig(port=port)
    grpc_transport = GrpcTransport(config=config, converter=converter)

    app = Modapp({grpc_transport})
    app.include_router(router)
    await app.run_async()
    try:
        yield app
    finally:
        await app.stop_async()


def import_module_by_path(module_path: Path):
    spec = importlib.util.spec_from_file_location(
        module_path.parent.as_posix(), module_path.as_posix()
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("localhost", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


@contextmanager
def proto_from_str(proto_str: str, proto_name: str, temp_dir_path: Path):
    old_cwd = os.getcwd()
    os.chdir(temp_dir_path)
    proto_file_path = temp_dir_path / f"p_{proto_name}.proto"
    with open(proto_file_path, "w") as proto_file:
        proto_file.write(proto_str)
    # generated files can import each other
    package_init_path = temp_dir_path / "__init__.py"
    package_init_path.touch()
    sys.path.insert(0, temp_dir_path.as_posix())

    grpc_tools.protoc.main(
        [
            "-I.",
            "--python_out=.",
            "--grpclib_python_out=.",
            proto_file_path.name,
        ]
    )

    p_pb_file_path = temp_dir_path / f"p_{proto_name}_pb2.py"
    p_pb_module = import_module_by_path(p_pb_file_path)
    p_grpc_file_path = temp_dir_path / f"p_{proto_name}_grpc.py"
    p_grpc_module = import_module_by_path(p_grpc_file_path)

    yield (p_pb_module, p_grpc_module)
    os.chdir(old_cwd)


class GrpcBlockingService:
    BlockingCall = RouteMeta(
        path="/modapp.tests.transports.grpc.GrpcBlockingService/BlockingCall",
        cardinality=Cardinality.UNARY_UNARY,
    )


class BlockingCallRequest(BaseModel):
    handler_id: int

    __modapp_path__ = "modapp.tests.transports.grpc.BlockingCallRequest"


class BlockingCallResponse(BaseModel):
    handler_id: int
    start_timestamp: int
    end_timestamp: int

    __modapp_path__ = "modapp.tests.transports.grpc.BlockingCallResponse"


def req_handler_with_long_duration(
    request: BlockingCallRequest,
) -> BlockingCallResponse:
    start_timestamp = round(time.time())
    while True:
        if time.time() - start_timestamp > 10:
            break
    end_timestamp = round(time.time())
    return BlockingCallResponse(
        handler_id=request.handler_id,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
    )


async def test_concurrency_blocking(tmp_path):
    logger.remove()
    logger.add(sys.stderr, level="TRACE")
    router = APIRouter()
    router.add_endpoint(
        GrpcBlockingService.BlockingCall, req_handler_with_long_duration
    )

    proto_str = """
syntax = "proto3";

package modapp.tests.transports.grpc;

message BlockingCallRequest {
  int32 handler_id = 1;
}

message BlockingCallResponse {
  int32 handler_id = 1;
  int32 start_timestamp = 2;
  int32 end_timestamp = 3;
}

service GrpcBlockingService {
  rpc BlockingCall(BlockingCallRequest)
      returns (BlockingCallResponse);
}
"""

    with proto_from_str(proto_str, "blocking", tmp_path) as (pb_module, grpc_module):
        protos = {
            "modapp.tests.transports.grpc.BlockingCallRequest": pb_module.BlockingCallRequest,
            "modapp.tests.transports.grpc.BlockingCallResponse": pb_module.BlockingCallResponse,
        }
        port = get_free_port()
        async with (
            grpc_modapp_server_with_router(router, protos, port),
            Channel("127.0.0.1", port) as channel,
        ):
            grpc_service = grpc_module.GrpcBlockingServiceStub(channel)

            calls = [
                grpc_service.BlockingCall(pb_module.BlockingCallRequest(handler_id=i))
                for i in range(multiprocessing.cpu_count())
            ]
            results = await asyncio.gather(*calls)

    # each end time should be before each start time
    # check by comparing the last(=max) start time and first(=min) end time
    max_start_timestamp = max([response.start_timestamp for response in results])
    min_end_timestamp = min([response.end_timestamp for response in results])
    assert max_start_timestamp < min_end_timestamp


class GrpcNonBlockingService:
    NonBlockingCall = RouteMeta(
        path="/modapp.tests.transports.grpc.GrpcNonBlockingService/NonBlockingCall",
        cardinality=Cardinality.UNARY_UNARY,
    )

class NonBlockingCallRequest(BaseModel):
    handler_id: int

    __modapp_path__ = "modapp.tests.transports.grpc.NonBlockingCallRequest"

class NonBlockingCallResponse(BaseModel):
    handler_id: int
    start_timestamp: int
    end_timestamp: int

    __modapp_path__ = "modapp.tests.transports.grpc.NonBlockingCallResponse"


async def req_handler_non_blocking(
    request: NonBlockingCallRequest,
) -> NonBlockingCallResponse:
    start_timestamp = round(time.time())
    await asyncio.sleep(10)
    end_timestamp = round(time.time())
    return NonBlockingCallResponse(
        handler_id=request.handler_id,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
    )


async def test_concurrency_non_blocking(tmp_path):
    logger.remove()
    logger.add(sys.stderr, level="TRACE")
    router = APIRouter()
    router.add_endpoint(GrpcNonBlockingService.NonBlockingCall, req_handler_non_blocking)
    
    proto_str = """
syntax = "proto3";

package modapp.tests.transports.grpc;

message NonBlockingCallRequest {
  int32 handler_id = 1;
}

message NonBlockingCallResponse {
  int32 handler_id = 1;
  int32 start_timestamp = 2;
  int32 end_timestamp = 3;
}

service GrpcNonBlockingService {
  rpc NonBlockingCall(NonBlockingCallRequest)
      returns (NonBlockingCallResponse);
}
"""

    with proto_from_str(proto_str, "non_blocking", tmp_path) as (
        pb_module,
        grpc_module,
    ):
        protos = {
            "modapp.tests.transports.grpc.NonBlockingCallRequest": pb_module.NonBlockingCallRequest,
            "modapp.tests.transports.grpc.NonBlockingCallResponse": pb_module.NonBlockingCallResponse,
        }
        port = get_free_port()
        async with (
            grpc_modapp_server_with_router(router, protos, port),
            Channel("127.0.0.1", port) as channel,
        ):
            grpc_service = grpc_module.GrpcNonBlockingServiceStub(channel)

            calls = [
                grpc_service.NonBlockingCall(
                    pb_module.NonBlockingCallRequest(handler_id=i)
                )
                for i in range(multiprocessing.cpu_count())
            ]
            results = await asyncio.gather(*calls)

    # each end time should be before each start time
    # check by comparing the last(=max) start time and first(=min) end time
    max_start_timestamp = max([response.start_timestamp for response in results])
    min_end_timestamp = min([response.end_timestamp for response in results])
    assert max_start_timestamp < min_end_timestamp


# TODO: test `run` as well, not only `run_async`
# TODO: test with max_workers=1 (=without multiprocessing)
