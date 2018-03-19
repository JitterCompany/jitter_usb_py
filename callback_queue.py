import queue


class CallbackQueue:

    def __init__(self):
        self._queue = queue.Queue()

    def poll(self):
        """ Call from the context you want the callbacks to run in"""
        result = False
        count=100
        try:
            while count:
                count-=1

                todo = self._queue.get(block=False)
                todo[0](*todo[1],**todo[2])
                result = True

        except queue.Empty:
            pass
        return result


    def wrap(self, func):
        """ wrap a func to be called by poll() (wrapper returns None)"""

        def _wrapped(*args, **kwargs):
            self._queue.put((func,args,kwargs))

        return _wrapped

