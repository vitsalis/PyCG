import pickle


class Plugin:
    def run(self):
        pass


def start(obj):
    if isinstance(obj, Plugin):
        obj.run()


start(pickle.loads(pickle.dumps(Plugin())))
