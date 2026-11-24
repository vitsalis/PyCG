def log(name):
    pass


class Audited:
    def __init__(self):
        self.value = 0

    def __setattr__(self, name, value):
        log(name)
        super().__setattr__(name, value)


audited = Audited()
audited.value = 1
