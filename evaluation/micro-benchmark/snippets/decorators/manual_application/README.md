A decorator is applied with an explicit call (`hello = shout(hello)`). After the
rebinding, `hello` is the wrapper, so the edge `main -> main.hello` must not
appear.
