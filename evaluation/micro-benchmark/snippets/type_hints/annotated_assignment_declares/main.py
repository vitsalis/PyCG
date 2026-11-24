import pickle


class Parser:
    def parse(self):
        pass


class Registry:
    def __init__(self, parsers):
        self.parsers: list[Parser] = pickle.loads(parsers)

    def run(self):
        for parser in self.parsers:
            parser.parse()


Registry(pickle.dumps([Parser()])).run()
