class Plugin:
    registry = []

    def __init_subclass__(cls):
        super().__init_subclass__()
        cls.registry.append(cls)


class Audio(Plugin):
    pass


class Video(Plugin):
    pass
