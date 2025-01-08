#!/bin/bash

from __future__ import print_function

import swampyer

import datetime
import time
import sys
import logging

logging.basicConfig(stream=sys.stdout, level=1)

try:
    client = swampyer.WAMPClient(
                    url="ws://NEXUS_HOST:8282/ws",
                    uri_base="com.example.wamp.api",
                ).start()


    for i in range(100):
        time_str = datetime.datetime.now().isoformat()
        print("Publishing to channel:",time_str)
        client.publish("time",args=[time_str])
        time.sleep(1)

except swampyer.SwampyException as ex:
    print("Whoops, something went wrong: {}".format(ex))


