
import typing
def build(meta: type[type]):
    return meta("C", (), {})
def alias(meta: typing.Type[type]):
    return meta("C", (), {})
