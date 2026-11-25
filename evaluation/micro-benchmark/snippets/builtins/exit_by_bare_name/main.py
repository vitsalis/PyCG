def stop(code):
    try:
        exit(code)
    except SystemExit:
        return code


stop(1)
