#!/usr/bin/python

# Unfortunately, it seems the crossbar folks have disabled
# their WAMP demo service. We'll connect anyways
# and simply get the error message

import time
import unittest

class Test(unittest.TestCase):
    def test_import(self):
        ex = None
        try:
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
        self.assertIsNone(ex,msg="Importing swampyer failed because {}".format(ex))

if __name__ == '__main__':
    unittest.main()



