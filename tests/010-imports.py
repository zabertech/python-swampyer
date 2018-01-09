#!/usr/bin/python

import unittest

class Test(unittest.TestCase):
    def test_import(self):
        ex = None
        try:
            import swampyer
        except Exception as ex:
            pass
        self.assertIsNone(ex,msg="Importing swampyer failed because {}".format(ex))

if __name__ == '__main__':
    unittest.main()



