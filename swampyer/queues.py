import time
import threading

from six.moves import queue

from .common import *
from .exceptions import *
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
        self.created_time = time.time()
        self.started_time = None
        self.ended_time = None

    def start(self, queue):
        """ We provide the Runner the queue to throw events against
            at the invocation time. It'd be annoying to the programmer
            to have to do so at invocation
        """
        self._queue = queue
        super(ConcurrencyRunner,self).start()

    def stats(self):

        runner_stats = {
            'created_time': self.created_time,
            'started_time': self.started_time,
            'ended_time': self.ended_time,
            'wait_duration': 0,
            'run_duration': 0,
        }

        # If started time is available, we can calculate
        # how long the runner had to wait before being allowed to execute
        # the invocation handler
        if self.started_time:
            runner_stats['waited_duration'] = self.started_time - self.created_time

        # If the ended time is available, we can calculate how long
        # the runner had to wait till it had results to send back to the
        # user
        if self.ended_time:
            runner_stats['run_duration'] = self.ended_time - self.started_time

        return runner_stats

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
            self.started_time = time.time()
            self.work()
        finally:
            self.ended_time = time.time()
            self._queue.put_exit(self)

class ConcurrencyEvent(object):
    def __init__(self, ev_type, runner=None):
        self.type = ev_type
        self.runner = runner
        self.id = runner and runner.concurrency_id

    def handle_error(self, ex):
        """ handle_error is only relevant if there's a runner associated
        """
        if self.runner:
            self.runner.handle_error(ex)

    def __getattr__(self, k):
        if self.runner:
            return getattr(self.runner,k)
        raise AttributeError('ConcurrencyEvent has no runner so no attribute {k}'.format(k))

    __getitem__ = __getattr__

class ConcurrencyQueue(threading.Thread):
    def __init__(self,
                queue_name=None,
                concurrency_max=0,
                queue_max=0,
                loop_timeout=0.1,
                _class=None,
                **kwargs
                ):
        super(ConcurrencyQueue,self).__init__()
        self.queue = queue.Queue()
        self.reset()
        self.queue_name = queue_name
        self.active = True
        self.daemon = True
        self.configure(
            concurrency_max = concurrency_max,
            queue_max = queue_max,
            loop_timeout = loop_timeout
        )
        self.init(**kwargs)

    def init(self,**kwargs):
        pass

    def configure(self, **kwargs):
        for k in ( 'concurrency_max', 'loop_timeout', 'queue_max' ):
            if k == 'concurrency_max':
                concurrency_max = kwargs[k]
                self.concurrency_max = concurrency_max
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
        self._stats = {
            'messages': 0,
            'run': 0,
            'waited': 0,
            'running': 0,
            'waiting': 0,
            'waitlist_max': 0,
            'rejected': 0,
            'errors': 0,
            'wait_duration': 0,
            'run_duration': 0,
            'wait_duration_avg': 0,
            'run_duration_avg': 0,
            'duration_datapoints': 0,
            'last_reset': time.time(),
        }

    def stats(self):
        """ Return the current stats object. Just a simple counter based
            report on what the client has been up to. Adds one parameter
            `timestamp` which holds the current epoch time
        """
        stats = self._stats.copy()
        stats['timestamp'] = time.time()

        if stats['duration_datapoints']:
            stats['wait_duration_avg'] = stats['wait_duration'] / stats['duration_datapoints']
            stats['run_duration_avg'] = stats['run_duration'] / stats['duration_datapoints']

        stats['running'] = self.active_count()
        stats['waiting'] = self.waitlist_count()

        return stats

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

    def waitlist_count(self):
        """ Returns the number of waiting threads
        """
        return len(self.waiting)

    def queue_full(self):
        """ Returns True if there is a max concurrency value for the
            queue and it happens to have been reached
        """
        if self.concurrency_max and self.active_count() >= self.concurrency_max:
            return True
        return False

    def waitlist_full(self):
        """ Returns True if the number of jobs waiting surpasses the allowed
            value in self.queue_max. If self.queue_max is 0, there's no limit
            to the number of jobs allowed to wait
        """
        if self.queue_max and self.waitlist_count() >= self.queue_max:
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
        self._stats['run'] += 1
        event.start(self)
        self.active_threads[event.id] = event

    def job_should_wait(self, event):
        return self.queue_full()

    def job_should_reject(self, event):
        return self.waitlist_full()

    def job_queued(self, event):
        """ Called when an event comes in that exceeds our current queue
            limit
        """
        pass

    def job_reject(self, event):
        """ Called when an event comes in that exceeds our waitlist
            limit and rejected. Once this function is called, the system
            will raise the ExWaitlistFull exeception
        """
        pass

    def queue_init(self, event):
        """ Triggered when a request for a new job is received by the queue
        """
        # If there is a limit
        #  If limit reached, queue for future invocation
        #  If limit not reached, start the runner
        if self.job_should_wait(event):

            # If we have hit the limit for maximum queues, we will throw
            # an error
            if self.job_should_reject(event):
                self._stats['rejected'] += 1
                self.job_reject(event)
                raise ExWaitlistFull("Queue {} waitlist full".format(self.queue_name))

            self._stats['waited'] += 1
            self.waiting.append(event)
            if len(self.waiting) > self._stats['waitlist_max']:
                self._stats['waitlist_max'] = len(self.waiting)
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

            # Add to stats how things went
            event_stats = event.stats()
            self._stats['wait_duration'] += event_stats['wait_duration']
            self._stats['run_duration'] += event_stats['run_duration']
            self._stats['duration_datapoints'] += 1

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
                    self._stats['messages'] += 1
                    self.queue_event(event)

                # Got an exception in the queueing, we need to pass
                # it on.
                except Exception as ex:
                    try:
                        self._stats['errors'] += 1
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

