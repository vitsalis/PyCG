def audit():
    pass


class audited(property):
    def __init__(self, fget):
        audit()
        super().__init__(fget)

    def __get__(self, instance, owner=None):
        return super().__get__(instance, owner)


class Config:
    @audited
    def name(self):
        return "c"


Config().name
