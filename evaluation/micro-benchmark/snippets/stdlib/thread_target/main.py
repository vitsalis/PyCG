import threading

def work():
    pass

thread = threading.Thread(target=work)
thread.start()
thread.join()
