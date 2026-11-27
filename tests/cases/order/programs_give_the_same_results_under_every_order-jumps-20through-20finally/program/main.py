
import ext
def f(): pass
def g(): pass
def run():
    handler = f
    while True:
        try:
            try:
                if ext.flag:
                    continue
                break
            finally:
                handler = g
        finally:
            if ext.done:
                return handler
    handler()
run()()
