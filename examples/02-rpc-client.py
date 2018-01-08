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

except swampyer.SwampyException as ex:
    print("Whoops, something went wrong: {}".format(ex))


