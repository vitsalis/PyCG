import socket
def reader(sock):
    sock.makefile("rb").read()
def writer(sock):
    sock.makefile(mode="wb").write(b"")
def text(sock):
    sock.makefile().readline()
def chosen(sock, mode):
    sock.makefile(mode).close()
def unknown(sock: socket.socket, mode):
    sock.makefile(mode).fileno()
def power():
    (2).__pow__(-1).is_integer()
    (2).__pow__(3).bit_length()
reader(socket.socket())
writer(socket.socket())
text(socket.socket())
chosen(socket.socket(), input())
power()
