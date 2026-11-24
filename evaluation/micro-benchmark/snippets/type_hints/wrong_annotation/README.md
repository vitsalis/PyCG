Python does not check annotations. The parameter is annotated as `Cat` but
receives an unrelated `Robot`, so the edge `main.talk -> main.Cat.speak` must
not appear.
