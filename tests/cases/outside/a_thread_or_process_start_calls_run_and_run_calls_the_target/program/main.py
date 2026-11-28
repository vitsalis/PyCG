import multiprocessing
import threading
class Item:
    def ping(self): pass
def work(item):
    item.ping()
def helper(): pass
class Looper(threading.Thread):
    def __init__(self):
        super().__init__(target=self.loop, args=(Item(),))
    def loop(self, item):
        item.ping()
class Plain(threading.Thread): pass
class Child(multiprocessing.Process):
    def run(self):
        helper()
def threads():
    threading.Thread(target=work, args=(Item(),)).start()
    Looper().start()
    Plain(target=helper).run()
def processes():
    multiprocessing.Process(target=work, kwargs={"item": Item()}).start()
    Child().start()
def another():
    threading.Thread(target=helper).start()
