class Config:
    pass

def fallback():
    pass

getattr(Config(), "loader", fallback)()
