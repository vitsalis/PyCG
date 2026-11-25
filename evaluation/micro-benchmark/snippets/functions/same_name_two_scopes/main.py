def first():
    def helper():
        pass
    helper()

def second():
    def helper():
        pass
    return helper

first()
second()
