import asyncio
import queue

from multiprocessing import Manager, cpu_count
from concurrent.futures import ThreadPoolExecutor
from typing import Any, cast


class QueueEnd:
    # just object() would not support multiprocessing, use class and compare by it
    def __eq__(self, other):
        return self.__class__ == other.__class__


class _ProcQueue:
    def __init__(self, q):
        self._queue: queue.Queue = q
        self._real_executor = None
        self._cancelled_join = False

    @property
    def _executor(self):
        if not self._real_executor:
            self._real_executor = ThreadPoolExecutor(max_workers=cpu_count())
        return self._real_executor

    def __getstate__(self):
        self_dict = self.__dict__
        self_dict["_real_executor"] = None
        return self_dict

    def qsize(self) -> int:
        return self._queue.qsize()

    def empty(self) -> bool:
        return self._queue.empty()

    def full(self) -> bool:
        return self._queue.full()

    def put(self, item) -> None:
        self._queue.put(item)

    def put_nowait(self, item) -> None:
        self._queue.put_nowait(item)
    
    def get(self) -> Any:
        return self._queue.get()

    def get_nowait(self) -> Any:
        return self._queue.get_nowait()

    def task_done(self) -> None:
        self._queue.task_done()

    async def put_async(self, item):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.put, item)

    async def get_async(self):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.get)


AsyncQueue = _ProcQueue


def create_async_process_queue(maxsize=0) -> AsyncQueue:
    m = Manager()
    q = m.Queue(maxsize=maxsize)
    return cast(AsyncQueue, _ProcQueue(q))
