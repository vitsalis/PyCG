class StorageError(Exception):
    def __init__(self, message="storage"):
        self.message = message


def read():
    try:
        {}["key"]
    except KeyError as error:
        raise StorageError("read failed") from error


def write():
    raise StorageError from None


for operation in (read, write):
    try:
        operation()
    except StorageError:
        pass
