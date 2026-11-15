class Greeter:
    def greet(self):
        pass

def get_greeter():
    return Greeter().greet

get_greeter()()
