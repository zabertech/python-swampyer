import threading
from six.moves import queue

from .common import *
from .utils import logger

ID_TRACKER = 0

class ConcurrencyRunner(threading.Thread):
    def __init__(self, handler, message):
        global ID_TRACKER
        super(ConcurrencyRunner, self).__init__()
        ID_TRACKER += 1
        self.concurrency_id = ID_TRACKER
        self.daemon = True
        self.handler = handler
        self.message = message

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

    def handle_error(self, ex):
        """ Triggered for whatever reason when handling this runner fails
        """
        pass

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

    def __getattr__(self, k):
        return getattr(self.runner,k)

    __getitem__ = __getattr__

class ConcurrencyQueue(threading.Thread):
    def __init__(self,
                max_concurrent=0,
                loop_timeout=0.1,
                **kwargs
                ):
        super(ConcurrencyQueue,self).__init__()
        self.queue = queue.Queue()
        self.reset()
        self.active = True
        self.daemon = True
        self.configure(
            max_concurrent = max_concurrent,
            loop_timeout = loop_timeout
        )
        self.init(**kwargs)

    def init(self,**kwargs):
        pass

    def configure(self, **kwargs):
        for k in ( 'max_concurrent', 'loop_timeout', ):
            if k == 'max_concurrent':
                max_concurrent = kwargs[k]
                self.max_concurrent = max_concurrent
                event = ConcurrencyEvent(EV_MAX_UPDATED)
                self.queue.put(event)

            elif k in kwargs:
                setattr(self,k,kwargs[k])

    def reset(self):
        """ When we need to expunge all the queues. This may happen
            when we're forced to reconnect
        """
        while not self.queue.empty():
            try:
                event = self.queue.get(False)
            except Empty:
                continue
            self.queue.task_done()
        self.active_threads = {}
        self.waiting = []

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

    def active_count(self):
        """ Returns the number of active threads
        """
        return len(self.active_threads)

    def waiting_count(self):
        """ Returns the number of waiting threads
        """
        return len(self.waiting)

    def queue_full(self):
        """ Returns True if there is a max concurrency value for the
            queue and it happens to have been reached
        """
        if self.max_concurrent and self.active_count() >= self.max_concurrent:
            return True
        return False

    def queue_empty(self):
        """ Returns a true value if both the active and the waiting
            queue are empty
        """
        if len(self.active_threads) or len(self.waiting):
            return False
        return True

    def transfer(self, current_queue):
        """ This takes an existing queue and transfers the queue data over
            to this instance. Typically used when replacing classes
        """
        current_queue.active = False
        self.waiting = current_queue.waiting

    def work_start(self, event):
        event.start(self)
        self.active_threads[event.id] = event

    def job_should_wait(self, event):
        return self.queue_full()

    def job_queued(self, event):
        """ Called when an event comes in that exceeds our current queue
            limit
        """
        pass

    def queue_init(self, event):
        """ Triggered when a request for a new job is received by the queue
        """
        # If there is a limit
        #  If limit reached, queue for future invocation
        #  If limit not reached, start the runner
        if self.job_should_wait(event):
            self.waiting.append(event)
            self.job_queued(event)
            return
        self.work_start(event)

    def queue_exit(self, event):
        """ Triggered when a running job completes
        """
        if event.id in self.active_threads:
            del self.active_threads[event.id]

    def queue_event(self, event):
        """ Triggered whenever an event is received on the event queue. Probably not
            that useful unless one wishes to manage queues entirely
        """
        # So there's an event, if it's to start something
        # If there's no concurrency limit, just start the runner
        if event.type == EV_INIT:
            self.queue_init(event)
            return

        # And captured an exit event.
        if event.type == EV_EXIT:
            self.queue_exit(event)

        # If the max concurrent has been updated or something
        # has finished running. Rescan the pending items to
        # see if we need to start any additional items
        if event.type in ( EV_EXIT, EV_MAX_UPDATED ):
            while self.waiting:
                if self.queue_full():
                    break
                waiting = self.waiting.pop(0)
                self.active_threads[waiting.id] = waiting
                self.work_start(waiting)

    def run(self):
        while self.active:
            try:
                event = self.queue.get(timeout=self.loop_timeout)
                try:
                    self.queue_event(event)

                # Got an exception in the queueing, we need to pass
                # it on.
                except Exception as ex:
                    try:
                        event.handle_error(ex)
                    # FIXME: what happens when the exception handler
                    # throws an exception?
                    except Exception as ex:
                        logger.warning("Exception handler failed: {}".format(ex))

            # If queue is empty, it's a timeout. We use the
            # opportunity to check if we've been requsested to drop
            # out of the loop
            except queue.Empty:
                pass

