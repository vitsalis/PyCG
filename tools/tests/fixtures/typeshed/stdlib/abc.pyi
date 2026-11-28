def abstractmethod(funcobj: _FuncT) -> _FuncT: ...

from typing import Callable, TypeVar

_FuncT = TypeVar("_FuncT", bound=Callable[..., object])
