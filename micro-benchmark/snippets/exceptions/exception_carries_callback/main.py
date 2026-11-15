def retry_fetch():
    pass


def retry_store():
    pass


class RetryError(Exception):
    def __init__(self, action):
        super().__init__()
        self.action = action


def fetch():
    raise RetryError(retry_fetch)


def store():
    raise RetryError(retry_store)


try:
    fetch()
except RetryError as error:
    error.action()
