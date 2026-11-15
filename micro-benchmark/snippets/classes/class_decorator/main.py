registry = []


def register(cls):
    registry.append(cls)
    return cls


@register
class Plugin:
    def __init__(self):
        pass


for plugin_class in registry:
    plugin_class()
