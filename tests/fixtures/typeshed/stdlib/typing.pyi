class _SpecialForm: ...

Any: _SpecialForm
Callable: _SpecialForm
Generic: _SpecialForm
Literal: _SpecialForm
Optional: _SpecialForm
Protocol: _SpecialForm
Self: _SpecialForm
Union: _SpecialForm

class TypeVar:
    def __init__(
        self, name: str, *constraints: object, bound: object = None
    ) -> None: ...

def overload(func: _F) -> _F: ...

_F = TypeVar("_F", bound=Callable[..., object])
AnyStr = TypeVar("AnyStr", str, bytes)
Text = str
