#!/usr/bin/python

import re
from lib import *

import swampyer
from swampyer.messages import *


def test_messages():

    # Validate that messages pass conditional tests when using
    # instance vs constant and class
    message = HELLO()
    assert message == WAMP_HELLO
    assert message == HELLO
    assert message != WAMP_WELCOME
    assert message != WELCOME

    """
    Using swampyer.messages.Messages.loads used to work assuming JSON based input.
    We've now moved to multiple serializers as well as the code is just *broken*
    so let's test that here.
    """
    valid_json = '[1, "izaber", "Nothing"]'

    # This line used to throw the exception:
    # `NameError: name 'self' is not defined`
    message = WampMessage.loads(valid_json)
    assert message == WAMP_HELLO

if __name__ == '__main__':
    test_messages()

