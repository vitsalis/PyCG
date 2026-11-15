import functools


class Cell:
    def set_state(self, state):
        pass

    set_alive = functools.partialmethod(set_state, True)
    set_dead = functools.partialmethod(set_state, False)


Cell().set_alive()
