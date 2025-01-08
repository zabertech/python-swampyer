#!/usr/bin/env python

import time
import logging
import sys

from lib import connect_service

import swampyer

logging.basicConfig(stream=sys.stdout, level=30)

def hello(event,data):
    return data

def test_reconnect():
    client = connect_service(auto_reconnect=True)
    client2 = connect_service()

    # Check if we can register
    reg_result = client.register(
                        'com.izaber.wamp.hello', hello,
                        details={"force_reregister": True},
                        concurrency_queue="unlimited",
                    )
    assert swampyer.WAMP_REGISTERED == reg_result
    assert reg_result == swampyer.WAMP_REGISTERED

    # Can we call data?
    call_result = client2.call('com.izaber.wamp.hello','something')
    assert call_result == 'something'

    # Let's now force a disconnection and see if it allows us to reconnect
    client.transport.close()

    # Allow it time to reconnect
    for i in range(40):
        time.sleep(1)

        # Then let's call the registration again
        try:
            call_result = client2.call('com.izaber.wamp.hello','something')
            assert call_result == 'something'
            break
        except swampyer.exceptions.ExInvocationError:
            pass
    else:
        assert False, "Failed to reconnect"

    # Then shutdown
    client.shutdown()
    client2.shutdown()

if __name__ == '__main__':
    test_reconnect()
