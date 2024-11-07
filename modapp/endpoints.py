from dataclasses import dataclass
from typing import AsyncIterator

import asyncio
import sys

from .models.dataclass import DataclassModel as BaseModel

connections_number = 0

async def keep_running(request: BaseModel) -> AsyncIterator[BaseModel]:
    global connections_number
    
    connections_number += 1
    
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        yield BaseModel()
    finally:
        connections_number -= 1
        if connections_number == 0:
            sys.exit(0)



@dataclass
class HealthCheckResponse(BaseModel):
    status: str
    
    __modapp_path__ = 'modapp.HealthCheckResponse'


async def health_check(request: BaseModel) -> HealthCheckResponse:
    return HealthCheckResponse(status='ok')
