import io
import tarfile


def archive():
    tarfile.open(fileobj=io.BytesIO(), mode="w").close()


archive()
