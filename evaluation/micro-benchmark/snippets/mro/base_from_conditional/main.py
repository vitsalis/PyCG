class Fast:
    def run(self):
        pass


class Safe:
    def run(self):
        pass


USE_FAST = True


class Runner(Fast if USE_FAST else Safe):
    pass


Runner().run()
