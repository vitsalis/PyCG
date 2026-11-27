def f(): pass
def g(): pass
class Tool:
    @staticmethod
    def run(cb=f): cb()
    @classmethod
    def make(cls, cb=f): cb()
def call(tool):
    tool.run(g)
    tool.make(g)
for tool in (Tool(), Tool(), Tool()):
    call(tool)
