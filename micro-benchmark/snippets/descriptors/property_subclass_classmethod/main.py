class classproperty(property):
    def __get__(self, instance, owner=None):
        return self.fget.__get__(None, owner)()


class Path:
    @classproperty
    @classmethod
    def next_class(cls):
        return cls

    def __init__(self, text):
        self.text = text

    def parent(self):
        return self.next_class(self.text)


class Root(Path):
    def __init__(self, text):
        self.text = text


Root("/").parent()
