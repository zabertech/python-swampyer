#!/usr/bin/python

import logging
import sys
import time

from lib import connect_service

import swampyer


logging.basicConfig(stream=sys.stdout, level=30)
# We want to see the protocol information
# being exchanged
#logging.basicConfig(stream=sys.stdout, level=1)

def hello(event,data):
    return data

def test_connection():
    client = connect_service('tcpip://NEXUS_HOST:18081')
    client2 = connect_service('tcpip://NEXUS_HOST:18081')

    # Check if we can register
    reg_result = client.register('com.izaber.wamp.hello', hello, details={"force_reregister": True})
    assert swampyer.WAMP_REGISTERED == reg_result
    assert reg_result == swampyer.WAMP_REGISTERED

    # Can we call data?
    call_result = client2.call('com.izaber.wamp.hello','something')
    assert call_result == 'something'

    # Let's unregister then
    unreg_result = client.unregister(reg_result.registration_id)
    assert unreg_result == swampyer.WAMP_UNREGISTERED

    # Can we subscribe?
    sub_data = {'data':None}
    def sub_capture(event,data):
        sub_data['data'] = data

    sub_result = client.subscribe('com.izaber.wamp.pub.hello', sub_capture)
    assert sub_result == swampyer.WAMP_SUBSCRIBED

    # And then publish
    pub_result = client2.publish(
            'com.izaber.wamp.pub.hello',
            options={
                'acknowledge': True,
                'exclude_me': False,
            },
            args=['Hej!']
        )
    assert pub_result == swampyer.WAMP_PUBLISHED

    # And check that we received the data
    time.sleep(0.1)
    assert sub_data['data'] == 'Hej!'

    # Unsubscribe
    unsub_result = client.unsubscribe(sub_result.subscription_id)
    assert unsub_result == swampyer.WAMP_UNSUBSCRIBED

    # Then shutdown one of the clients
    client2.shutdown()
    client.shutdown()


if __name__ == '__main__':
    test_connection()

