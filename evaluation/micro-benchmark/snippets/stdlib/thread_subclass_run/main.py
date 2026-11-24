import threading

class Worker(threading.Thread):
    def run(self):
        pass

worker = Worker()
worker.start()
worker.join()
