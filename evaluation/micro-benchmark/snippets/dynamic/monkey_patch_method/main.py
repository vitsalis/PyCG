class Greeter:
    def greet(self):
        pass

def loud_greet(self):
    pass

Greeter.greet = loud_greet
Greeter().greet()
