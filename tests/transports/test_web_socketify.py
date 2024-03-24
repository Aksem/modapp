from typing import AsyncGenerator

import aiohttp
import pytest

from modapp.validators.pydantic import PydanticValidator
from modapp.converters.protobuf import ProtobufConverter
from modapp.transports.web_socketify import (
    WebSocketifyTransport,
    WebSocketifyTransportConfig,
)
from modapp.server import Modapp


@pytest.fixture
async def modapp_app() -> AsyncGenerator[Modapp, None]:
    converter = ProtobufConverter(protos={}, validator=PydanticValidator())
    config = WebSocketifyTransportConfig()
    web_transport = WebSocketifyTransport(config=config, converter=converter)

    app = Modapp({web_transport})
    await app.run_async()
    try:
        yield app
    finally:
        await app.stop_async()


async def test_auth(modapp_app: Modapp):
    async with aiohttp.ClientSession() as session:
        async with session.post('http://127.0.0.1:3000/auth') as resp:
            response_body = await resp.json()

    assert len(response_body['id']) == 20
