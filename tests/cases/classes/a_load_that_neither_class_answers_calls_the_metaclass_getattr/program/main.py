
def handler(): pass
class Meta(type):
    def __getattr__(cls, name):
        cls.known()
        return handler
    def known(cls): pass
class Api(metaclass=Meta):
    @classmethod
    def present(cls): pass
def use():
    Api.anything()
    Api.present()
    Api.known()
