
import os
import sys
import pool_lib
from pool_lib import pool
class Writer:
    def __init__(self):
        self.paths = os.path
        self.stream = sys.stdout
        self.pool = pool
        self.client = pool_lib.Client()
    def emit(self, x):
        self.paths.join(x)
        # A standard stream is an io.TextIOWrapper.
        self.stream.write(x)
    def query(self):
        conn = self.pool.conn
        conn.execute()
        self.client.send()
def join(a, b):
    path = os.path
    return path.join(a, b)
