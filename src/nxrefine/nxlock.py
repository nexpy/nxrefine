import os
import time
import timeit


class LockException(Exception):
    LOCK_FAILED = 1


class Lock(object):

    def __init__(self, filename, timeout=600, check_interval=1):
        self.filename = os.path.realpath(filename)
        self.lock_file = self.filename+'.lock'
        self.timeout = timeout
        self.check_interval = check_interval
    
    def acquire(self, timeout=None, check_interval=None):
        if timeout is None:
            timeout = self.timeout
        if timeout is None:
            timeout = 0

        if check_interval is None:
            check_interval = self.check_interval

        def _get_lock():
            if os.path.exists(self.lock_file):
                raise LockException("'%s' already locked" % self.filename)
            else:
                open(self.lock_file, 'w').write("%s" % os.getpid())
        try:
            _get_lock()
        except LockException as exception:
            timeoutend = timeit.default_timer() + timeout
            while timeoutend > timeit.default_timer():
                time.sleep(check_interval)
                try:
                    _get_lock()
                    break
                except LockException:
                    pass
            else:
                raise LockException("'%s' already locked" % self.filename)

    def release(self):
        if os.path.exists(self.lock_file):
            os.remove(self.lock_file)

    def __enter__(self):
        return self.acquire()

    def __exit__(self, type_, value, tb):
        self.release()

    def __delete__(self, instance):
        instance.release()
