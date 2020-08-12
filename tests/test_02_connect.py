#!/usr/bin/python

from common import *
import logging
import sys

import swampyer


# We want to see the protocol information
# being exchanged
logging.basicConfig(stream=sys.stdout, level=1)

def connect_service():
    client = swampyer.WAMPClientTicket(
                    url="ws://localhost:18080/ws",
                    username="test",
                    password=get_password(),
                    realm="realm1",
                    uri_base="",
                ).start()
    #result = client.register('com.izaber.wamp.hello', hello)
    #client.publish('com.izaber.wamp.heylisten',{'acknowledge':True},['Hej!'])
    return 'OK'

def test_connection():
    assert connect_service() == 'OK'


    
if __name__ == '__main__':
    print(connect_service())
