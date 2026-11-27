
import tarfile
def through_module(path):
    tarfile.open(path).close()
def through_class(path):
    tarfile.TarFile.open(path).close()
through_module("a.tar")
through_class("a.tar")
