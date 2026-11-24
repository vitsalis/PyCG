def lookup(key):
    pass


class Registry:
    def __class_getitem__(cls, key):
        return lookup(key)


Registry["audio"]
