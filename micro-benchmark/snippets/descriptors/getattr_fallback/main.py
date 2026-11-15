def fallback():
    pass


class Proxy:
    def known(self):
        pass

    def __getattr__(self, name):
        return fallback


def use_known(proxy):
    proxy.known()


def use_missing(proxy):
    proxy.missing()


proxy = Proxy()
use_known(proxy)
use_missing(proxy)
