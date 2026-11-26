class Rows:
    def index(self, value):
        return 0


class Pairs:
    def index(self, value):
        return 0


class Table:
    def __init__(self):
        self._headers = Rows()

    def get_headers(self):
        return self._headers

    def set_headers(self, value):
        pass

    headers = property(get_headers, set_headers)


table = Table()
table.headers = Pairs()
table.headers.index(1)
