class Playlist:
    def __init__(self):
        self.songs = ["a", "b"]

    def __len__(self):
        return len(self.songs)


len(Playlist())
