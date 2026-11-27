
import logging
import re
import threading
import typing
from typing import Optional
def use(
    logger: logging.Logger,
    pattern: "re.Pattern[str]",
    event: Optional[threading.Event],
    names: list[str],
    kind: type[ValueError],
    items: typing.Iterable[str],
):
    logger.info("x")
    pattern.match("x")
    event.wait()
    names[0].upper()
    kind("x")
    # An abstract type does not fix the class: no edge.
    items.no_such_method()
