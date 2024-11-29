#!/usr/bin/python

import logging
import sys
import time

from lib import connect_service
import threading
import swampyer


logging.basicConfig(stream=sys.stdout, level=30)
# We want to see the protocol information
# being exchanged
#logging.basicConfig(stream=sys.stdout, level=1)

"""
The following function keeps track of the number concurrent
invocations are active based upon the `queue_name` keyword.
As the TRACKER and TRACKER_MAX are global we simply increment
went entering and decrement when going out. TRACKER_MAX just
detects when TRACKER has an amount greater than previously
recorded and we use that as an external means to detect when
we have more than the allowed number of concurrent invocations
active
"""
TRACKER = {}
TRACKER_MAX = {}
INVOKE_TRACKER = {}
INVOKE_TRACKER_MAX = {}

def simple_invoke(event, queue_name, bypass):
    TRACKER.setdefault(queue_name,0)
    TRACKER_MAX.setdefault(queue_name,0)
    TRACKER[queue_name] += 1
    if TRACKER[queue_name] > TRACKER_MAX[queue_name]:
        TRACKER_MAX[queue_name] = TRACKER[queue_name]

    INVOKE_TRACKER.setdefault(queue_name,0)
    INVOKE_TRACKER_MAX.setdefault(queue_name,0)
    INVOKE_TRACKER[queue_name] += 1
    if INVOKE_TRACKER[queue_name] > INVOKE_TRACKER_MAX[queue_name]:
        INVOKE_TRACKER_MAX[queue_name] = INVOKE_TRACKER[queue_name]

    time.sleep(0.5)

    TRACKER[queue_name] -= 1
    INVOKE_TRACKER[queue_name] -= 1

    return queue_name

SUB_TRACKER = {}
SUB_TRACKER_MAX = {}
def simple_subscribe(event, queue_name, bypass):
    TRACKER.setdefault(queue_name,0)
    TRACKER_MAX.setdefault(queue_name,0)
    TRACKER[queue_name] += 1
    if TRACKER[queue_name] > TRACKER_MAX[queue_name]:
        TRACKER_MAX[queue_name] = TRACKER[queue_name]

    SUB_TRACKER.setdefault(queue_name,0)
    SUB_TRACKER_MAX.setdefault(queue_name,0)
    SUB_TRACKER[queue_name] += 1
    if SUB_TRACKER[queue_name] > SUB_TRACKER_MAX[queue_name]:
        SUB_TRACKER_MAX[queue_name] = SUB_TRACKER[queue_name]

    time.sleep(0.5)

    TRACKER[queue_name] -= 1
    SUB_TRACKER[queue_name] -= 1

    return queue_name

CALL_ERRORS = {}
def simple_call(client, method, bypass):
    def make_call():
        try:
            call_result = client.call('com.izaber.wamp.hello.'+method,method,bypass)
            assert call_result == method
        except swampyer.ExInvocationError as ex:
            CALL_ERRORS.setdefault(method,0)
            CALL_ERRORS[method] += 1

    return make_call

def invoke_a_bunch(methods, iterations):
    """ This will invoke each of the methods `iterations` times 
        in quick succession. Then waits for the threads to complete
    """
    thread_list = []
    for i in range(iterations):
        for method in methods:
            thr = threading.Thread(target=method)
            thr.start()
            thread_list.append(thr)

    # Wait till it's done
    for thr in thread_list:
        thr.join()

# swampyer.ConcurrencyQueue can be subclassed to modify the
# behaviour by which we all 
class CustomQueue1(swampyer.ConcurrencyQueue):
    """ This overrides the max_concurrent value of unlimited
        and manually forces a limit of 2 concurrent
    """
    def queue_full(self):
        if self.active_count() >= 2:
            return True
        return False

class CustomQueue2(swampyer.ConcurrencyQueue):
    """ This will log all jobs that get waited upon
    """
    def init(self):
        self.queued_jobs = {}

    def job_queued(self, event):
        details = event.message.details
        procedure = details['procedure']
        self.queued_jobs.setdefault(procedure,0)
        self.queued_jobs[procedure] += 1

    def queue_full(self):
        if self.active_count() >= 2:
            return True
        return False


    def job_should_wait(self, event):
        message = event.message

        # We have two possibilities. One is an invoke (to start
        # a function) the other an event for a subscription
        if message == swampyer.WAMP_INVOCATION:

            # In the case of a procedure, if the 2nd element
            # of the args array is True, we will bypass the
            # queue limit check and immediately run the invocation
            if message.args[1]:
                return False

        elif message == swampyer.WAMP_EVENT:
            print(message.dump())

        return self.queue_full()

class CustomQueue3(swampyer.ConcurrencyQueue):
    """ This overrides the max_concurrent value of unlimited
        and manually forces a limit of 2 concurrent
        This will also set a max of 5 waiting connections
        before it starts throwing errors at the user
    """
    def init(self, custom):
        self.custom = custom

    def job_should_wait(self, event):
        if self.active_count() >= 2:
            return True
        return False

    def queue_init(self, event):
        if self.waitlist_count() >= 5:
            raise Exception("Exceeded waitlist counts")
        super(CustomQueue3,self).queue_init(event)


def reset_trackers():
    TRACKER.clear()
    TRACKER_MAX.clear()
    INVOKE_TRACKER.clear()
    INVOKE_TRACKER_MAX.clear()
    SUB_TRACKER.clear()
    SUB_TRACKER_MAX.clear()
    CALL_ERRORS.clear()

def test_connection():
    client = connect_service(
                  timeout=60,
                  concurrency_class=CustomQueue1
              )
    client2 = connect_service(timeout=60)

    # --------------------------------------------------------------
    # Check if we can register
    reg_result = client.register(
                      'com.izaber.wamp.hello.default',
                      simple_invoke,
                      details={
                          "force_reregister": True,
                          "match": u"prefix",
                      },
                  )
    assert swampyer.WAMP_REGISTERED == reg_result
    assert reg_result == swampyer.WAMP_REGISTERED

    # Let's create a burst of data
    invoke_a_bunch([simple_call(client2, 'default', False)],10)

    # What was the maximum number of concurrent connections?
    assert TRACKER_MAX['default'] == 2

    # Should have no call errors
    assert len(CALL_ERRORS) == 0

    client.shutdown()

    # --------------------------------------------------------------
    # Clear the trackers since we're going to do new
    # a new set of runs
    reset_trackers()

    # New queue, new client
    client = connect_service(
                  timeout=60,
                  concurrency_class=CustomQueue2
              )

    # Register new function
    reg_result = client.register(
                      'com.izaber.wamp.hello.default',
                      simple_invoke,
                      details={
                          "force_reregister": True,
                          "match": u"prefix",
                      },
                  )
    assert swampyer.WAMP_REGISTERED == reg_result
    assert reg_result == swampyer.WAMP_REGISTERED

    # Validate that we're empty of errors
    assert len(CALL_ERRORS) == 0

    # Let's create a burst of data and we're going to bypass some
    # gates due to the custom queue
    invoke_a_bunch(
        [
            simple_call(client2, 'default', False),
            simple_call(client2, 'default', True),
        ],
        10
    )

    # Due to timings and other vaguaries, we don't actually
    # except to be able to get an exact number for the maximum
    # concurrent processes. We do expect to get more than the
    # default maximum of 2

    # What was the maximum number of concurrent connections?
    assert TRACKER_MAX['default'] > 2, "Expected >2 got {}".format(TRACKER_MAX['default'])

    # We launch 20 jobs but 10 of them bypass the queue. So we expect
    # up to 10 jobs to be queued. We're also testing that we can capture
    # events custom
    custom_queue = client.concurrency_queue_get('default')
    assert custom_queue.queued_jobs['com.izaber.wamp.hello.default'] <= 10

    # Should have no call errors
    assert len(CALL_ERRORS) == 0

    client.shutdown()

    # --------------------------------------------------------------
    # Clear the trackers since we're going to do new
    # a new set of runs
    reset_trackers()

    # New queue, new client
    client = connect_service(
                  timeout=60,
                  concurrency_configs={
                      'default': {
                        'custom': 'custom value',
                        '_class': CustomQueue3
                      }
                  }
              )

    # Register new function
    reg_result = client.register(
                      'com.izaber.wamp.hello.default',
                      simple_invoke,
                      details={
                          "force_reregister": True,
                          "match": u"prefix",
                      },
                  )
    assert swampyer.WAMP_REGISTERED == reg_result
    assert reg_result == swampyer.WAMP_REGISTERED

    # Can we pass custom values through?
    assert client.concurrency_queue_get('default').custom == 'custom value'

    # Let's create a burst of data and we're going to bypass some
    # gates due to the custom queue
    invoke_a_bunch(
        [
            simple_call(client2, 'default', False),
        ],
        20
    )

    # Should have some call errors
    assert len(CALL_ERRORS) > 0
    assert CALL_ERRORS['default'] > 1

    # Then shutdown
    client.shutdown()
    client2.shutdown()

if __name__ == '__main__':
    test_connection()

