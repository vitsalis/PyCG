import copy


class Handler:
    def handle(self):
        pass


def process(handler: Handler) -> None:
    handler.handle()


prototype = Handler()
process(copy.copy(prototype))
