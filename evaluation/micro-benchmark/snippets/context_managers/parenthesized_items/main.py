class Reader:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        pass


class Writer:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def write(self):
        pass


with (
    Reader() as reader,
    Writer() as writer,
):
    reader.read()
    writer.write()
