import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, AsyncIterator

import aiohttp

# import pytest_asyncio

from modapp import APIRouter
from modapp.client import BaseChannel
from modapp.converters.json import JsonConverter
from modapp.models.pydantic import PydanticModel
from modapp.transports.web_aiohttp import WebAiohttpTransport
from modapp.transports.web_aiohttp_config import WebAiohttpTransportConfig
from modapp.routing import RouteMeta, Cardinality
from modapp.server import Modapp
from modapp.transports.utils.free_port import get_free_port


class ListNotesRequest(PydanticModel):
    __modapp_path__ = "modapp.tests.transports.aiohttp.ListNotesRequest"


class Note(PydanticModel):
    content: str

    __modapp_path__ = "modapp.tests.transports.aiohttp.Note"


class ListNotesResponse(PydanticModel):
    notes: list[Note]

    __modapp_path__ = "modapp.tests.transports.aiohttp.ListNotesResponse"


class GenerateNotesRequest(PydanticModel):
    count: int

    __modapp_path__ = "modapp.tests.transports.aiohttp.GenerateNotesRequest"


class AiohttpService:
    ListNotes = RouteMeta(
        path="/modapp.tests.transports.aiohttp.AiohttpService/ListNotes",
        cardinality=Cardinality.UNARY_UNARY,
    )
    
    GenerateNotes = RouteMeta(
        path='/modapp.tests.transports.aiohttp.AiohttpService/GenerateNotes',
        cardinality=Cardinality.UNARY_STREAM
    )


router = APIRouter()


@router.endpoint(AiohttpService.ListNotes)
async def list_notes(request: ListNotesRequest) -> ListNotesResponse:
    return ListNotesResponse(notes=[Note(content="don't forget to test your code")])


@router.endpoint(AiohttpService.GenerateNotes)
async def generate_notes(request: GenerateNotesRequest) -> AsyncIterator[Note]:
    for i in range(0, request.count):
        yield Note(content=f'{i}')
        await asyncio.sleep(1)


# @pytest_asyncio.fixture
# async def modapp_app() -> AsyncGenerator[Modapp, None]:
#     converter = JsonConverter()
#     config = AiohttpTransportConfig()
#     web_transport = AiohttpTransport(config=config, converter=converter)

#     app = Modapp({web_transport})
#     app.include_router(router)
#     await app.run_async()
#     try:
#         yield app
#     finally:
#         app.stop()


@asynccontextmanager
async def create_app() -> AsyncGenerator[tuple[Modapp, int], None]:
    converter = JsonConverter()
    free_port = get_free_port()
    config = WebAiohttpTransportConfig(port=free_port)
    web_transport = WebAiohttpTransport(config=config, converter=converter)

    app = Modapp({web_transport},
                 # endpoints temporarily used in test_server
                 keep_running_endpoint=True, healthcheck_endpoint=True)
    app.include_router(router)
    await app.run_async()
    try:
        yield app, free_port
    finally:
        app.stop()


async def test_unary_unary_returns_data():
    # app creation is currently implemented as context manager because in case of using asyncio_fixture,
    # app stays blocked during execution of the test. Need to be investigated and changed
    async with create_app() as (_, port):
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"http://127.0.0.1:{port}/modapp/tests/transports/Aiohttp/Aiohttpservice/listnotes",
            ) as resp:
                response_body = await resp.json()

        assert response_body == {
            "notes": [{"content": "don't forget to test your code"}]
        }


class AiohttpClientServiceCls:
    async def generate_notes(
        self, channel: BaseChannel, request: GenerateNotesRequest
    ) -> AsyncIterator[Note]:
        return channel.send_unary_stream(
            "/modapp.tests.transports.aiohttp.AiohttpService/GenerateNotes",
            request,
            Note,
        )


async def test_unary_stream_returns_all_messages():
    # it's not fair test because we use aiohttp channel here, but let it be e2e test for now
    from modapp.channels.aiohttp import AioHttpChannel

    async with create_app() as (_, port):
        converter = JsonConverter()
        async with AioHttpChannel(
            converter=converter, server_address=f"http://127.0.0.1:{port}"
        ) as channel:
            service = AiohttpClientServiceCls()
            request = GenerateNotesRequest(count=3)

            iterator = await service.generate_notes(channel=channel, request=request)
            notes: list[Note] = [note async for note in iterator]

            assert notes == [
                Note(content='0'),
                Note(content='1'),
                Note(content='2'),
            ]
