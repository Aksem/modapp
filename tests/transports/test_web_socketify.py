from contextlib import asynccontextmanager
from typing import AsyncGenerator

import aiohttp

# import pytest_asyncio

from modapp import APIRouter
from modapp.converters.json import JsonConverter
from modapp.models.pydantic import PydanticModel
from modapp.transports.web_socketify import (
    WebSocketifyTransport,
    WebSocketifyTransportConfig,
)
from modapp.routing import RouteMeta, Cardinality
from modapp.server import Modapp


class ListNotesRequest(PydanticModel):
    __modapp_path__ = "modapp.tests.transports.WebSocketify.ListNotesRequest"


class Note(PydanticModel):
    content: str

    __modapp_path__ = "modapp.tests.transports.WebSocketify.Note"


class ListNotesResponse(PydanticModel):
    notes: list[Note]

    __modapp_path__ = "modapp.tests.transports.WebSocketify.ListNotesResponse"


class WebSocketifyService:
    ListNotes = RouteMeta(
        path="/modapp.tests.transports.WebSocketify.WebSocketifyService/ListNotes",
        cardinality=Cardinality.UNARY_UNARY,
    )


router = APIRouter()


@router.endpoint(WebSocketifyService.ListNotes)
async def list_notes(request: ListNotesRequest) -> ListNotesResponse:
    return ListNotesResponse(notes=[Note(content="don't forget to test your code")])


# @pytest_asyncio.fixture
# async def modapp_app() -> AsyncGenerator[Modapp, None]:
#     converter = JsonConverter()
#     config = WebSocketifyTransportConfig()
#     web_transport = WebSocketifyTransport(config=config, converter=converter)

#     app = Modapp({web_transport})
#     app.include_router(router)
#     await app.run_async()
#     try:
#         yield app
#     finally:
#         app.stop()


@asynccontextmanager
async def create_app() -> AsyncGenerator[Modapp, None]:
    converter = JsonConverter()
    config = WebSocketifyTransportConfig()
    web_transport = WebSocketifyTransport(config=config, converter=converter)

    app = Modapp({web_transport})
    app.include_router(router)
    await app.run_async()
    try:
        yield app
    finally:
        app.stop()


async def test_unary_unary_returns_data():
    # app creation is currently implemented as context manager because in case of using asyncio_fixture,
    # app stays blocked during execution of the test. Need to be investigated and changed
    async with create_app():
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://127.0.0.1:3000/modapp/tests/transports/websocketify/websocketifyservice/listnotes",
            ) as resp:
                response_body = await resp.json()

        assert response_body == {
            "notes": [{"content": "don't forget to test your code"}]
        }
