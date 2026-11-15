import copy


class Config:
    def __copy__(self):
        return Config()

    def __deepcopy__(self, memo):
        return Config()


config = Config()
copy.copy(config)
copy.deepcopy(config)
