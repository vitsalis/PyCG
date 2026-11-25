def release():
    pass


class Resource:
    def __del__(self):
        release()


resource = Resource()
del resource
