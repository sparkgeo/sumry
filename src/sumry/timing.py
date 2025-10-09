from functools import wraps
from time import time

class Timer:
    def __init__(self, name):
        self.name = name

    def __enter__(self):
        self.start_time = time()

    def __exit__(self, type, value, traceback):
        delta = time() - self.start_time
        self.delta = delta
        self.start_time = None

        msg = f"{self.name}: {delta:.3f}s"
        if traceback:
            msg += " (with error)"
        print(msg)


def timing(name=None):
    def decorator(f):
        @wraps(f)
        def wrap(*args, **kw):
            ts = time()
            result = f(*args, **kw)
            te = time()
            func_name = name if name else f.__name__
            print("func:%r took: %2.4f sec" % (func_name, te - ts))
            return result

        return wrap

    return decorator
