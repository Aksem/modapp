import asyncio
from pathlib import Path
from typing import Callable

from loguru import logger
from watchfiles import arun_process, PythonFilter


async def main(path: Path, func: Callable):
    logger.info(f"Start watching: {str(path)}")
    await arun_process(path, target=func, watch_filter=PythonFilter())


def run_and_watch(path: Path, func: Callable):
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main(path, func))
    except KeyboardInterrupt:
        ...
