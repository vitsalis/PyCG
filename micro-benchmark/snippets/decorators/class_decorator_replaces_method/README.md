A class decorator replaces a method with a wrapper that calls the original. The
method call runs the wrapper, so the edge `main -> main.Engine.start` must not
appear.
