import functools
import typing
import sys

try:
    # anyio is optional dependency
    import anyio.to_thread
except ImportError:
    anyio = None

if sys.version_info >= (3, 10):  # pragma: no cover
    from typing import ParamSpec
else:  # pragma: no cover
    from typing_extensions import ParamSpec


P = ParamSpec("P")
T = typing.TypeVar("T")


async def run_in_threadpool(
    func: typing.Callable[P, T], *args: P.args, **kwargs: P.kwargs
) -> T:
    if kwargs:  # pragma: no cover
        # run_sync doesn't accept 'kwargs', so bind them in here
        func = functools.partial(func, **kwargs)
    
    if anyio is None:
        raise Exception('Install modapp with anyio dependency to be able to run background tasks')
    
    return await anyio.to_thread.run_sync(func, *args)
