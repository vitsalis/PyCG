The argument comes from a library call (`copy.copy`), so data flow inside the
snippet does not give its type. The parameter annotation names the class, and
it is correct here.
