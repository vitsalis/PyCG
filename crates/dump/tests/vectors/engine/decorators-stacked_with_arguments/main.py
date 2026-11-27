def tag(name):
    def decorator(func):
        def wrapper():
            return func()

        return wrapper

    return decorator


@tag("outer")
@tag("inner")
def render():
    pass


render()
