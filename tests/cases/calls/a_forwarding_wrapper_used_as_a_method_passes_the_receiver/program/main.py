
def forward(f):
    def wrapper(*args, **kwargs):
        return f(*args, **kwargs)
    return wrapper
class Base:
    @forward
    def run(self):
        self.step()
    def step(self): pass
class Child(Base):
    def step(self): pass
Base().run()
Child()
