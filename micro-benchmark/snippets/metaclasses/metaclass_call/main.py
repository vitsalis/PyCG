class Singleton(type):
    def __call__(cls, *args):
        if not hasattr(cls, "instance"):
            cls.instance = super().__call__(*args)
        return cls.instance


class Config(metaclass=Singleton):
    def __init__(self):
        pass


Config()
Config()
