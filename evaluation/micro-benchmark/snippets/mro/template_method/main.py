class Pipeline:
    def run(self):
        self.load()
        self.transform()

    def load(self):
        pass

    def transform(self):
        pass


class Upper(Pipeline):
    def transform(self):
        pass


Upper().run()
