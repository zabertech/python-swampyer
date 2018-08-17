import random
import time

sysrand = random.SystemRandom()

class FIELD(object):
    default = None

    def __init__(self, name, default=None, required=True):
        self.name = name
        if default:
            self.default = default
        self.value = None
        self.required = required

    def default_value(self):
        return self.default

class URI(FIELD):
    default = ''

class DICT(FIELD):
    default = {}
    def default_value(self):
        return dict(self.default)

class STRING(FIELD):
    default = ''

class CODE(FIELD):
    default = None

class ID(FIELD):
    default = None
    def default_value(self):
        # Use the size from Javascript:
        # https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Number/MAX_SAFE_INTEGER
        return sysrand.randint(1,9007199254740991)

class LIST(FIELD):
    default = []
    def default_value(self):
        return list(self.default)

