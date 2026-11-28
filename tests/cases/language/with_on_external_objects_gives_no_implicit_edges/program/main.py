
import ext
def read(path):
    with open(path) as file, ext.connection as connection:
        file.read()
        connection.close()
