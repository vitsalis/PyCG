from contextlib import ExitStack


def close_file():
    pass


def close_socket():
    pass


class Resource:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


with ExitStack() as stack:
    stack.enter_context(Resource())
    stack.callback(close_file)
