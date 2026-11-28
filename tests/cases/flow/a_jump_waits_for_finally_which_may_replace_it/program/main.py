
def f(): pass
def g(): pass
def h(): pass

import ext
def returned():
    while True:
        try:
            break
        finally:
            return
    f()
def replaced():
    handler = f
    while True:
        try:
            break
        finally:
            handler = g
    handler()
def kept_kind():
    handler = f
    while True:
        try:
            continue
        finally:
            handler = g
    handler()
def nested():
    handler = f
    while True:
        try:
            try:
                break
            finally:
                handler = g
        finally:
            ext.cleanup()
    handler()
def nested_leaves():
    while True:
        try:
            try:
                break
            finally:
                ext.cleanup()
        finally:
            return
    f()
def from_handler():
    for item in ext.items:
        try:
            ext.run()
        except ValueError:
            continue
        finally:
            break
        f()
    g()
