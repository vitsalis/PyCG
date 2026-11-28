
import pathlib
Failure = PythonFinalizationError | None
MaybePath = pathlib.Path | None
def report(error: Failure, path: MaybePath):
    error.add_note("details")
    path.exists()
