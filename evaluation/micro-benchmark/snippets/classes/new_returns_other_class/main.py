class Real:
    def __init__(self):
        pass


class Proxy:
    def __new__(cls):
        return Real()

    def __init__(self):
        pass


Proxy()
