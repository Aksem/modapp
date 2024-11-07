import asyncio
from contextlib import suppress
from dataclasses import dataclass

import aiohttp
from modapp.client import BaseChannel, Stream
from modapp.converters.json import JsonConverter
import pytest
from .transports.test_aiohttp import create_app
from modapp.channels.aiohttp import AioHttpChannel
from modapp.models.dataclass import DataclassModel as BaseModel



@dataclass
class KeepRunningUntilDisconnectRequest(BaseModel):
    __modapp_path__ = "modapp.KeepRunningUntilDisconnectRequest"


@dataclass
class KeepRunningUntilDisconnectResponse(BaseModel):
    __modapp_path__ = "modapp.KeepRunningUntilDisconnectResponse"


class AiohttpClientServiceCls:
    async def keep_running_until_disconnect(
        self, channel: BaseChannel, request: KeepRunningUntilDisconnectRequest
    ) -> Stream[KeepRunningUntilDisconnectResponse]:
        return await channel.send_unary_stream(
            "/modapp.ModappService/KeepRunningUntilDisconnect",
            request,
            KeepRunningUntilDisconnectResponse,
        )


async def test_keep_running_and_health_check():
    async with create_app() as (_, port):
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"http://127.0.0.1:{port}/modapp/modappservice/gethealthstatus",
            ) as resp:
                response_text = await resp.text()
                print(response_text)
                response_body = await resp.json()
                assert response_body["status"] == "ok"

            # converter = JsonConverter()
            
            # exited = False
            # try:
            # with pytest.raises(SystemExit):
            #     async with AioHttpChannel(
            #         converter=converter, server_address=f"http://127.0.0.1:{port}"
            #     ) as channel:
            #         service = AiohttpClientServiceCls()
            #         request = KeepRunningUntilDisconnectRequest()
            #         iterator = await service.keep_running_until_disconnect(channel=channel, request=request)
            #         await asyncio.sleep(3)
            #         print('end iterator')
            #         await iterator.end()
            #         print('iterator ended')

            # with pytest.raises(SystemExit):
            #     await asyncio.sleep(3)
            # print('after wait time')
