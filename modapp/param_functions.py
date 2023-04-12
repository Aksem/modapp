from typing import Any, Callable, Iterator, Optional, TypeVar

from modapp import params


def Meta() -> Any:
    return params.Meta()


DependencyReturnType = TypeVar("DependencyReturnType")


def Depends(
    dependency: Optional[Callable[..., Iterator[DependencyReturnType]]] = None,
    use_cache: bool = True,
) -> DependencyReturnType:
    return params.Depends(dependency=dependency, use_cache=use_cache)
