
import typing
def instance(a: tuple[()]):
    a.count(1)
def alias(a: typing.Tuple[()]):
    a.count(1)
def kind(k: type[tuple[()]]):
    k()
def optional_kind(k: typing.Optional[type[tuple[()]]]):
    k()
