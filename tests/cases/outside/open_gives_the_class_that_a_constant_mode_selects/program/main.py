
import io
import os
import pathlib
def text():
    open("p").close()
def text_mode():
    open("p", "rt").close()
def updated_text():
    open("p", mode="a+").close()
def read():
    open("p", "rb").close()
def write():
    open("p", mode="wb").close()
def append():
    open("p", "ab", -1).close()
def exclusive():
    open("p", "xb").close()
def update():
    open("p", "r+b").close()
def raw():
    open("p", "rb", 0).close()
def raw_by_keyword():
    open("p", "wb", buffering=0).close()
def line_buffered():
    io.open("p", "w", 1).close()
def descriptor():
    os.fdopen(3, "rb").close()
def path():
    pathlib.Path("p").open("wb").close()
def path_text():
    pathlib.Path("p").open().close()
text()
text_mode()
updated_text()
read()
write()
append()
exclusive()
update()
raw()
raw_by_keyword()
line_buffered()
descriptor()
path()
path_text()
