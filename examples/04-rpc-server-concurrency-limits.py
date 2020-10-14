#!/bin/bash

from __future__ import print_function

import swampyer

import time
import sys
import logging

logging.basicConfig(stream=sys.stdout, level=1)

def simple_concurrency():
    """ This is an example where we set two different registered URIs

        - a URI that will have a the default concurrency limit that lets
            it run only one at a time. We set a default global concurrency
            limit to "1" when instantiating the client object. This global
            concurrency limit is shared between all registrations and subscriptions.
            If a more granular approach is required, have a look at this file's
            second example.

        - a second URI that will not be limited concurrency-wise. This is
            achieved by setting the concurrency queue that it uses to "unlimited"

    """
    client = swampyer.WAMPClient(
                    url="ws://localhost:8282/ws",
                    uri_base="com.example.wamp.api",
                    concurrency_max=1 # By default all registrations, subscriptions can
                                      # run single threaded (and they get queued) globally
                ).start()

    def hello_world(*args, **kwargs):
        print("Received Args:{} Kwargs:{}".format(args,kwargs))
        return "Hello there!"

    # This URI uses the global concurrency limit
    client.register("hello", hello_world)

    # This one uses the unlimited queue (so no concurrency limit at all)
    client.register("hello2", hello_world, concurrency_queue="unlimited")

def targetted_concurrency():
    """ This is an example where we set multiple URIs with differing concurrency policies

        1. a URI that will have a the default concurrency limit that lets
            it run only one at a time. We set a default global concurrency
            limit to "1" when instantiating the client object. This global
            concurrency limit is shared between all registrations and subscriptions.

        2. a URI that will not be limited to a higher value of 5. This is achieved
            by providing a hash to the `concurrency_max` argument at client instantiation.
            All registrations/subscriptions sharing a queue_name will also share concurrency.

        3. a URI that will not be limited concurrency-wise. This is
            achieved by setting the concurrency queue that it uses to "unlimited"

        4. a URI that will use the default concurrency maximum (of 1). When providing
            a keyed concurrency max with a value of "None" it will use the default value.
            This is useful when the desire is to let the concurrency limit be controlled
            by the default value but create another pool of concurrency items

        The code will also demonstrate how to change the concurrency limits dynamically

        
    """
    client = swampyer.WAMPClient(
                    url="ws://localhost:8282/ws",
                    uri_base="com.example.wamp.api",
                    concurrency_max={
                      'default': 1,
                      'new-queue': 5,
                      'use_default': None,
                    },
                ).start()

    def hello_world(*args, **kwargs):
        print("Received Args:{} Kwargs:{}".format(args,kwargs))
        return "Hello there!"

    # This URI uses the global concurrency limit. By default the "default"
    # concurrency_queue is implied
    client.register("hello", hello_world)

    # This one uses the second queue named "new-queue"
    client.register("hello2", hello_world, concurrency_queue="new-queue")

    # The unlimited queue also exists and is created automatically
    client.register("hello3", hello_world, concurrency_queue="unlimited")

    # The 'use_default' queue because it is set to None will use the default
    # settings of '1'
    client.register("hello4", hello_world, concurrency_queue="use_default")

    # Change the concurrency limit for `new-queue` from 5 to 50
    # If limit goes up,
    client.configure(concurrency_max={
                          'new-queue': 50
                      })

    # By default supplying names that have not previously been defined
    # in `concurrency_max` will throw the ExNotImplemented error
    try:
        client.register("hello5", hello_world, concurrency_queue="nonexisting")
    except NotImplementedError:
        pass

    # However, if the key `concurrency_strict_naming` is set to false. It will
    # create a new queue based upon the default value
    client.configure(concurrency_strict_naming=False)

    # This should then be okay
    client.register("hello5", hello_world, concurrency_queue="nonexisting")


def concurrency_events(*args, **kwargs):
    """ By subclassing swampyer.ConcurrencyQueue, it's possible to manage
        how subscription events and invocations get handed over to the
        handlers.

        In this example, a new class `CustomQueue` is created. It will:

        - Have a default queue size of 5
        - Throw errors once the wait queue grows to 100 (rejects the call)
        - Any procedure that has `bypass` in the URI will skip the queue
        - Log the maximum number of waiting events

    """

    class CustomQueue(swampyer.ConcurrencyQueue):

        def init(self, max_allowed=100):
            self.max_waiting = 0
            self.max_allowed = max_allowed
        
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

            return super(CustomQueue,self).job_should_wait(event)

        def queue_init(self, event):

            waiting_jobs = self.waiting_count()

            # Check and log if the number of waiting jobs reaches a new high
            if waiting_jobs > self.max_waiting:
                self.max_waiting = waiting_jobs

            # Then check if the jobs is `self.max_allowed` or more. If so, we throw and error
            # that will get sent back to the client making the call
            if waiting_jobs >= self.max_allowed:
                raise Exception("Exceeded waiting counts")

            # Otherwise proceed normally
            super(CustomQueue,self).queue_init(event)

    my_queue = CustomQueue( 
                  max_concurrent=5,
                  max_allowed=100
                )

    client = swampyer.WAMPClient(
                    url="ws://localhost:8282/ws",
                    uri_base="com.example.wamp.api",
                    concurrency_queues={
                      'default': my_queue
                    }
                ).start()


try:

    # Run for 1 minute then quiet
    time.sleep(60)

except swampyer.SwampyException as ex:
    print("Whoops, something went wrong: {}".format(ex))


