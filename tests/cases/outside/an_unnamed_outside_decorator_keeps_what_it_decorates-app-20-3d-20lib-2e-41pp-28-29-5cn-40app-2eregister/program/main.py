import lib
app = lib.App()
@app.register
def job(): pass
app = lib.App()
@app.register
class Model:
    def run(self): pass
def use():
    job()
    Model().run()
