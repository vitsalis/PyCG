def return_func():
    def nested_return_func():
        pass
    return nested_return_func

def func():
    return return_func

func()()
func()()()
