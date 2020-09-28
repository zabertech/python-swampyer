import threading
from six.moves import queue

from .common import *

ID_TRACKER = 0

class ConcurrencyRunner(threading.Thread):
    def __init__(self):
        global ID_TRACKER
        super(ConcurrencyRunner, self).__init__()
        ID_TRACKER += 1
        self.concurrency_id = ID_TRACKER
        self.daemon = True

    def start(self, queue):
        """ We provide the Runner the queue to throw events against
            at the invocation time. It'd be annoying to the programmer
            to have to do so at invocation
        """
        self._queue = queue
        super(ConcurrencyRunner,self).start()

    def work(self):
        """ Override this function!
        """
        raise NotImplementedError("The 'work' function must be overriden!")

    def run(self):
        """ This wraps the run so that we can catch when the
            thread finishes
        """
        try:
            self.work()
        finally:
            self._queue.put_exit(self)

class ConcurrencyEvent(object):
    def __init__(self, ev_type, runner=None):
        self.type = ev_type
        self.runner = runner
        self.id = runner and runner.concurrency_id

    def start(self, queue):
        self.runner.start(queue)

class ConcurrencyQueue(threading.Thread):
    def __init__(self, max_concurrent=0,loop_timeout=0.1):
        super(ConcurrencyQueue,self).__init__()
        self.active = True
        self.active_threads = {}
        self.waiting = []
        self.queue = queue.Queue()
        self.daemon = True
        self.configure(
            max_concurrent = max_concurrent,
            loop_timeout = loop_timeout
        )

    def configure(self, **kwargs):
        for k in ( 'max_concurrent', 'loop_timeout', ):
            if k == 'max_concurrent':
                max_concurrent = kwargs[k]
                self.max_concurrent = max_concurrent
                event = ConcurrencyEvent(EV_MAX_UPDATED)
                self.queue.put(event)

            elif k in kwargs:
                setattr(self,k,kwargs[k])

    def put(self, runner):
        """ Notify the concurrency loop that we'd like to start a thread
        """
        event = ConcurrencyEvent(EV_INIT,runner)
        self.queue.put(event)

    def put_exit(self, runner):
        """ Notify the concurrency loop that a thread has been finished
        """
        event = ConcurrencyEvent(EV_EXIT,runner)
        self.queue.put(event)

    def queue_full(self):
        """ Returns True if there is a max concurrency value for the
            queue and it happens to have been reached
        """
        if self.max_concurrent and len(self.active_threads) >= self.max_concurrent:
            return True
        return False

    def run(self):
        while self.active:

            try:
                event = self.queue.get(timeout=self.loop_timeout)

                # So there's an event, if it's to start something
                # If there's no concurrency limit, just start the runner
                # If there is a limit
                #  If limit reached, queue for future invocation
                #  If limit not reached, start the runner
                if event.type == EV_INIT:
                    if self.queue_full():
                        self.waiting.append(event)
                        continue
                    self.active_threads[event.id] = event
                    event.start(self)
                    continue

                # And captured an exit event.
                if event.type == EV_EXIT:
                    del self.active_threads[event.id]

                # If the max concurrent has been updated or something
                # has finished running. Rescan the pending items to
                # see if we need to start any additional items
                if event.type in ( EV_EXIT, EV_MAX_UPDATED ):
                    while self.waiting:
                        if self.queue_full(): break
                        waiting = self.waiting.pop(0)
                        self.active_threads[waiting.id] = waiting
                        waiting.start(self)


            # If queue is empty, it's a timeout. We use the
            # opportunity to check if we've been requsested to drop
            # out of the loop
            except queue.Empty:
                pass

