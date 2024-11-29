#!/usr/bin/env python

import time
import logging
import sys

from lib import connect_service

import swampyer


logging.basicConfig(stream=sys.stdout, level=30)

def hello(event,data):
    return data

def test_connection():
    client = connect_service()
    client2 = connect_service()

    # Check if we can register
    reg_result = client.register('com.izaber.wamp.hello', hello, details={"force_reregister": True})
    assert swampyer.WAMP_REGISTERED == reg_result
    assert reg_result == swampyer.WAMP_REGISTERED

    # Can we call data?
    call_result = client2.call('com.izaber.wamp.hello','something')
    assert call_result == 'something'

    # Send some binary data
    binary_data = b'\xEF\xBB\xBF\x00'
    call_result = client2.call('com.izaber.wamp.hello',binary_data)
    assert call_result
    assert call_result.encode('utf8') == binary_data

    # Let's send a huge amount of data
    binary_data = b'\xEF\xBB\xBF\x00'*1000000
    call_result = client2.call('com.izaber.wamp.hello',binary_data)
    assert call_result
    assert call_result.encode('utf8') == binary_data

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

    # We had an issue where multiple publishes in a row took
    # longer and longer. In this case we'll run the query
    # 100 times quickly than see how much time has passed
    # This should take less than 1 second
    start_time = time.time()
    for _ in range(30):
        pub_result = client2.publish(
            'com.izaber.wamp.pub.hello',
            options={
                'acknowledge': True,
            },
            args=['Hej!']
        )
    end_time = time.time()
    duration = end_time - start_time
    assert duration < 1.0

    # Then shutdown
    client.shutdown()
    client2.shutdown()



if __name__ == '__main__':
    test_connection()

