import asyncio
from pathlib import Path
from typing import Callable

import isort
from command_runner import command_runner
from loguru import logger
from watchfiles import awatch, PythonFilter
from watchfiles.run import detect_target_type, start_process


async def main(path: Path, func: Callable):
    logger.info(f"Start watching: {str(path)}")
    # await arun_process(
    #     path, target=func, watch_filter=PythonFilter(), callback=on_change
    # )

    target_type = detect_target_type(func)
    process = None

    try:
        while True:
            logger.trace("Start application")
            process = start_process(func, target_type, args=(), kwargs={})
            changes = []
            async for changed_files in awatch(path, watch_filter=PythonFilter()):
                changes = changed_files
                break
            process.stop()

            filepaths = [file_change[1] for file_change in changes]
            filepaths_str = "\n".join(filepaths)
            logger.trace("Changed files:" + "\n" + filepaths_str)

            logger.trace("Sorting imports in changed files")
            # exit_code, output = command_runner(
            #     f'poetry run isort {" ".join(filepaths)}', shell=True
            # )
            # print(exit_code, output)
            for filepath in filepaths:
                isort.file(filepath)

            logger.trace("Format changed files")
            exit_code, output = command_runner(
                f'poetry run black {" ".join(filepaths)}', shell=True
            )
            print(exit_code, output)

            logger.trace("Check types in whole project after changes")
            exit_code, output = command_runner(
                f"poetry run mypy --strict {(path / 'xide_server').as_posix()}",
                shell=True,
            )
            print(exit_code, output)
    except KeyboardInterrupt:
        if process is not None:
            process.stop()
        print("stopped")


def run_and_watch(path: Path, func: Callable):
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main(path, func))
    except KeyboardInterrupt:
        ...
