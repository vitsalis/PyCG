
import ctypes
import xmlrpc.client
def use(proxy: xmlrpc.client.ServerProxy):
    proxy.system_listMethods()
    ctypes.cdll.libc.getpid()
