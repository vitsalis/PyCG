A generator function decorated with `contextlib.contextmanager`. The call
`managed()` runs the library wrapper, which calls the generator function; the
`with` statement runs the generator up to and after the `yield`.
