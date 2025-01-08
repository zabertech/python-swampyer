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
def simple_invoke(event, queue_name):
    global TRACKER
    TRACKER.setdefault(queue_name,0)
    TRACKER_MAX.setdefault(queue_name,0)
    TRACKER[queue_name] += 1
    if TRACKER[queue_name] > TRACKER_MAX[queue_name]:
        TRACKER_MAX[queue_name] = TRACKER[queue_name]
    time.sleep(0.5)
    TRACKER[queue_name] -= 1
    return queue_name

CALL_ERRORS = {}
def simple_call(client, method):
    def make_call():
        try:
            call_result = client.call('com.izaber.wamp.hello.'+method,method)
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


def reset_trackers():
    TRACKER.clear()
    TRACKER_MAX.clear()
    CALL_ERRORS.clear()


def test_connection():
    # For concurrency, the queues must be defined in advance.
    # This is partly because this forces the setting of the queue size before
    # things can get messy
    # For instance, if we allow queue sizes to be defined at registration call
    # we could have conflicts like
    #
    # client.reg('foo',call,maxsize=1000000,concurrency_queue='default')
    # client.reg('foo2',call,maxsize=1,concurrency_queue='default')
    #
    # Which is correct?
    # So while the policy is a bit blunt, we force the definition of the
    # queue size at session creation
    client = connect_service(
                  concurrency_max=2,
                  timeout=60
              )
    client2 = connect_service(timeout=60)

    # --------------------------------------------------------------
    # Check if we can register
    reg_result = client.register(
                      'com.izaber.wamp.hello.default',
                      simple_invoke,
                      details={
                          "force_reregister": True,
                      },
                  )
    assert swampyer.WAMP_REGISTERED == reg_result
    assert reg_result == swampyer.WAMP_REGISTERED

    # Let's create a burst of data
    invoke_a_bunch([simple_call(client2, 'default')],10)

    # What was the maximum number of concurrent connections?
    assert TRACKER_MAX['default'] == 2

    # Let's unregister then
    unreg_result = client.unregister(reg_result.registration_id)
    assert unreg_result == swampyer.WAMP_UNREGISTERED

    # --------------------------------------------------------------
    # Okay, so let's register a new entry that can have unlimited
    reg_result = client.register(
                      'com.izaber.wamp.hello.unlimited',
                      simple_invoke,
                      details={"force_reregister": True},
                      concurrency_queue="unlimited",
                  )
    assert swampyer.WAMP_REGISTERED == reg_result
    assert reg_result == swampyer.WAMP_REGISTERED

    # Let's create a burst of data
    invoke_a_bunch([simple_call(client2, 'unlimited')],10)

    # What was the maximum number of concurrent connections?
    # Since this was to an unlimited call queue, it should hit 10
    assert TRACKER_MAX['unlimited'] == 10

    # Unregister the previous function
    unreg_result = client.unregister(reg_result.registration_id)
    assert unreg_result == swampyer.WAMP_UNREGISTERED

    # --------------------------------------------------------------
    # Clear the trackers since we're going to do new
    # a new set of runs
    reset_trackers()

    # Let's create another client with multiple queues
    concurrency_configs = {
        'just2': {
            'concurrency_max': 2,
            'queue_max': 10,
        },
        'just5': {
            'concurrency_max': 5,
        },
        'just10': {
            'concurrency_max': 10,
        },
    }
    client3 = connect_service(concurrency_configs=concurrency_configs,timeout=60)
    for k in concurrency_configs.keys():
        reg_result = client3.register(
                          'com.izaber.wamp.hello.'+k,
                          simple_invoke,
                          details={"force_reregister": True},
                          concurrency_queue=k,
                      )
        assert swampyer.WAMP_REGISTERED == reg_result
        assert reg_result == swampyer.WAMP_REGISTERED

    # Let's create a burst of data
    invoke_a_bunch([
        simple_call(client2,k) for k in concurrency_configs.keys()
    ],50)

    # Match the max concurrency amounts with what we expect them to be
    for k,v in concurrency_configs.items():
        expected = v['concurrency_max']
        assert TRACKER_MAX[k] <= expected, "Expected less than or equal to {} got {}".format(expected, TRACKER_MAX[k])

    # Since we've put a queue_max on the just2 queue, we expect some
    # errors as well
    assert CALL_ERRORS['just2'] > 0
    assert CALL_ERRORS.get('just5',0) == 0
    assert CALL_ERRORS.get('just10',0) == 0

    # --------------------------------------------------------------
    # Let's amend the concurrency limits to new ones
    concurrency_updates = {
        'just2': 20,
        'just5': 10,
        'just10': 30,
    }
    for queue_name, new_limit in concurrency_updates.items():
        concurrency_queue = client3.concurrency_queue_get(queue_name)
        concurrency_queue.configure(concurrency_max=new_limit)

    # Let's create a burst of data
    invoke_a_bunch([
        simple_call(client2,k) for k in concurrency_configs.keys()
    ],50)

    # Match the max concurrency amounts with what we expect them to be
    for k,v in concurrency_updates.items():
        assert TRACKER_MAX[k] <= v, "Expected less than or equal to {} got {}".format(v, TRACKER_MAX[k])

    # --------------------------------------------------------------
    # By default we don't allow auto creation of new concurrency queues
    def unmadequeue():
        return client3.register(
                          'com.izaber.wamp.hello.fake',
                          simple_invoke,
                          details={"force_reregister": True},
                          concurrency_queue='unmadequeue',
                      )
    try:
        unmadequeue()
        raise Exception("What, this shouldn't happen")
    except Exception as ex:
        assert isinstance(ex, swampyer.ExNotImplemented)

    # --------------------------------------------------------------
    # But it we update the client to allow it, it should happen
    client3.configure(concurrency_strict_naming=False)
    reg_result = unmadequeue()
    assert swampyer.WAMP_REGISTERED == reg_result
    assert reg_result == swampyer.WAMP_REGISTERED


    # Then shutdown
    client.shutdown()
    client2.shutdown()
    client3.shutdown()


    
if __name__ == '__main__':
    test_connection()

