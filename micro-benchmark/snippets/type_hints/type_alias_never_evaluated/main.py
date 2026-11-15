def make_handler_type():
    return int


type Handler = make_handler_type()


def handle(value: Handler) -> None:
    pass


handle(1)
