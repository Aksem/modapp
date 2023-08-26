from typing import Any, Callable, Iterator, TypeVar, cast

from modapp import params


def Meta() -> Any:
    return params.Meta()


DependencyReturnType = TypeVar("DependencyReturnType")


def Depends(
    dependency: Callable[..., Iterator[DependencyReturnType]],
    use_cache: bool = True,
) -> DependencyReturnType:
    return cast(
        DependencyReturnType, params.Depends(dependency=dependency, use_cache=use_cache)
    )
