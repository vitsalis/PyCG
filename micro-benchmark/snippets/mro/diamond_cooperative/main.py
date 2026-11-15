class Root:
    def setup(self):
        pass


class Left(Root):
    def setup(self):
        super().setup()


class Right(Root):
    def setup(self):
        super().setup()


class Both(Left, Right):
    def setup(self):
        super().setup()


Both().setup()
