def handler():
    pass


class Meta(type):
    def __getattr__(cls, name):
        return handler


class Api(metaclass=Meta):
    pass


Api.anything()
