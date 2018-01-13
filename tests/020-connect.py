#!/usr/bin/python

import time
import websocket
import unittest
import logging
import sys

try:
    import crossbar
    from crossbar.controller.cli import run
except ImportError:
    print "Can't test due to lack of crossbar"
    sys.exit()

websocket.enableTrace(True)

root = logging.getLogger()
root.setLevel(1)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
root.addHandler(ch)

class Test(unittest.TestCase):
    def test_import(self):
        ex = None
        try:
            # Launch Crossbar

            import swampyer
            client = swampyer.WAMPClient(
                            #url="ws://localhost:8282/ws"
                            url="wss://demo.crossbar.io/ws",
                            realm="realm1",
                        ).start()

            time.sleep(1)

        except swampyer.exceptions.ExAbort as expectedException:
            pass
        except Exception as ex:
            pass
        self.assertIsNone(ex,msg="Swampyer connect failed because {}".format(ex))

if __name__ == '__main__':
    unittest.main()



