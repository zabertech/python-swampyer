#!/usr/bin/python

import logging
import sys

from lib import connect_service
import swampyer


logging.basicConfig(stream=sys.stdout, level=30)
# We want to see the protocol information
# being exchanged
#logging.basicConfig(stream=sys.stdout, level=1)

# If a windows socket error 10054 WSAECONNRESET is caught, raise
# ExWAMPConnectionError and treat it like any other disconnection
# If we don't, this creates a nasty spin lock condition

import swampyer.transport
import swampyer.exceptions

RECV_DATA_ITERATIONS = 0

@swampyer.transport.register_transport('myws')
class WebsocketTransport(swampyer.WebsocketTransport):
    throw_errors = False

    def __init__(self, url, **options):
        # Remove the 'my' portion of myws
        url =  url[2:]
        super(WebsocketTransport, self).__init__(url,**options)

    def recv_data(self, control_frame=True):
        global RECV_DATA_ITERATIONS
        if self.throw_errors:
            RECV_DATA_ITERATIONS += 1
            raise OSError(10054,"Fake OSEerror")
        return super(WebsocketTransport,self).recv_data(control_frame)

    def next(self):
        global RECV_DATA_ITERATIONS
        if RECV_DATA_ITERATIONS > 100:
            raise swampyer.exceptions.ExWAMPConnectionError("Too many iterations")
        return super(WebsocketTransport,self).next()

def hello(event,data):
    return data

def test_exception():
    client = connect_service(url='myws://NEXUS_HOST:8282/ws')

    # Check if we can register
    reg_result = client.register('com.izaber.wamp.hello', hello, details={"force_reregister": True})
    assert swampyer.WAMP_REGISTERED == reg_result
    assert reg_result == swampyer.WAMP_REGISTERED

    client.transport.throw_errors = True

    logging.disable(logging.CRITICAL)
    logging.getLogger('swampyer').disabled = True
    try:
        client.register('com.izaber.wamp.hello', hello, details={"force_reregister": True}) 
    except Exception:
        pass
    logging.disable(logging.NOTSET)
    logging.getLogger('swampyer').disabled = False

    # So when we try and read from the socket, if the bug is in effect, the
    # os will generate the 10054 error. That creates an incredibly fast churn
    # loop when what we actually want is to have the system just bail out on the
    # first pass.
    assert client.transport == None
    assert RECV_DATA_ITERATIONS == 1

    # Then shutdown
    client.shutdown()

    
if __name__ == '__main__':
    test_exception()

