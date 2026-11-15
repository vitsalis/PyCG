class Root:
    def setup(self):
        pass


class Left(Root):
    def setup(self):
        super().setup()


class Right(Root):
    def setup(self):
        pass


class Both(Left, Right):
    pass


Left().setup()
