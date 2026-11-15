class Engine:
    def start(self):
        pass


def pick_base():
    return Engine


class Car(pick_base()):
    pass


Car().start()
