
import lib
class Task(lib.Base):
    pass
def use():
    Task().run()
    try:
        pass
    except lib.Error as error:
        error.details()
