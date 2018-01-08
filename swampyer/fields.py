import time

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
        """ We cheat, we just use the millisecond timestamp for the request
        """
        millis = int(round(time.time() * 1000))
        return millis

class LIST(FIELD):
    default = []
    def default_value(self):
        return list(self.default)

