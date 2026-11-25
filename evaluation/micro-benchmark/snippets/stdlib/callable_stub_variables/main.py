import shutil
import tempfile
import timeit

start = timeit.default_timer()
shutil.rmtree(tempfile.mkdtemp())
