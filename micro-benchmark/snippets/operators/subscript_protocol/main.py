class Grid:
    def __getitem__(self, key):
        return 0

    def __setitem__(self, key, value):
        pass

    def __delitem__(self, key):
        pass


grid = Grid()
grid[0] = 1
grid[0]
grid[1:2]
del grid[0]
