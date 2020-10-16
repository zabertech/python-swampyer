#!/bin/bash

from __future__ import print_function

import swampyer

import time
import sys
import logging

logging.basicConfig(stream=sys.stdout, level=1)

try:
    client = swampyer.WAMPClient(
                    url="ws://localhost:8282/ws",
                    uri_base="com.example.wamp.api",
                ).start()

    print(client.call("hello"))

    # Print some basic stats on what was done
    #
    # client.stats() returns a dict of:
    # 
    # messages: number of WAMP messages received
    # invocations: invocations messages received
    # calls: calls made
    # events: publication events received
    # publications: publications made
    # errors: error messages received
    # last_reset: epoch time of last reset of stats
    # 
    print(client.stats())

except swampyer.SwampyException as ex:
    print("Whoops, something went wrong: {}".format(ex))


