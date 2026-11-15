import ext

connections = {"db": ext.connect()}
connections["db"].close()
