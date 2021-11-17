
import sys
import six
import decimal
import traceback

from .fields import *
from .serializers import *

OPT = {'required': False}

MESSAGE_TYPES = dict(
    HELLO        = [ CODE('code',1), URI('realm'), DICT('details') ],
    WELCOME      = [ CODE('code',2), ID('session_id'), DICT('details') ],
    ABORT        = [ CODE('code',3), DICT('details'), URI('reason') ],
    CHALLENGE    = [ CODE('code',4), STRING('auth_method'), DICT('extra') ],
    AUTHENTICATE = [ CODE('code',5), STRING('signature', hide_from_debug=True), DICT('extra') ],
    GOODBYE      = [ CODE('code',6), DICT('details'), URI('reason') ],
    ERROR        = [ CODE('code',8), CODE('request_code'), ID('request_id'),
                      DICT('details'), URI('error',**OPT),
                      LIST('args',**OPT),DICT('kwargs',**OPT) ],

    PUBLISH      = [ CODE('code',16), ID('request_id'), DICT('options'), URI('topic'),
                      LIST('args',**OPT),DICT('kwargs',**OPT) ],
    PUBLISHED    = [ CODE('code',17), ID('request_id'), ID('publication_id') ],

    SUBSCRIBE    = [ CODE('code',32), ID('request_id'), DICT('options'), URI('topic') ],
    SUBSCRIBED   = [ CODE('code',33), ID('request_id'), ID('subscription_id') ],
    UNSUBSCRIBE  = [ CODE('code',34), ID('request_id'), ID('subscription_id') ],
    UNSUBSCRIBED = [ CODE('code',35), ID('request_id') ],

    EVENT        = [ CODE('code',36), ID('subscription_id'), ID('publish_id'), DICT('details'),
                      LIST('args',**OPT), DICT('kwargs',**OPT) ],

    CALL         = [ CODE('code',48), ID('request_id'), DICT('options'), URI('procedure'),
                      LIST('args',**OPT), DICT('kwargs',**OPT) ],
    RESULT       = [ CODE('code',50), ID('request_id'), DICT('details'),
                      LIST('args',**OPT), DICT('kwargs',**OPT) ],

    REGISTER     = [ CODE('code',64), ID('request_id'), DICT('details'), URI('procedure') ],
    REGISTERED   = [ CODE('code',65), ID('request_id'), ID('registration_id') ],
    UNREGISTER   = [ CODE('code',66), ID('request_id'), ID('registration_id') ],
    UNREGISTERED = [ CODE('code',67), ID('request_id'), DICT('details') ],

    INVOCATION   = [ CODE('code',68), ID('request_id'), ID('registration_id'), DICT('details'),
                      LIST('args',**OPT), DICT('kwargs',**OPT) ],

    YIELD        = [ CODE('code',70), ID('request_id'), DICT('options'),
                      LIST('args',**OPT), DICT('kwargs',**OPT) ],
)
MESSAGE_CLASS_LOOKUP = {}
MESSAGE_NAME_LOOKUP = {}

class WampMessage(object):
    _fields = []     # autoset
    code_name = None # autoset
    serializer = None # autoset

    def __init__(self,**kwargs):
        self.serializer = kwargs.pop('serializer',load_serializer('json'))
        for field in self._fields:
            name = field.name
            setattr(
                self,
                name,
                kwargs.get(
                    name,
                    field.default_value()
                )
            )

    @staticmethod
    def load(data):
        # First column in list is always WAMP type code
        if not data: return
        message_code = data[0]
        message_class = MESSAGE_CLASS_LOOKUP[message_code]
        return message_class().unpackage(data)

    @staticmethod
    def loads(data_str, serializer=None):
        # If we're calling from another message, let's use that message's 
        data = load_serializer(serializer or 'json').loads(data_str)
        if not data: return
        # First column in list is always WAMP type code
        message_code = data[0]
        message_class = MESSAGE_CLASS_LOOKUP[message_code]
        return message_class().unpackage(data)


    def unpackage(self,data):
        if len(data) > len(self._fields):
            raise ExMessageCorrupt("Data has too many fields for this record type '{}' with {}".format(self.code_name,data))
        for i in range(len(data)):
            field = self._fields[i]
            value = data[i]
            self[field.name] = value
        return self

    def package(self, debug=False):
        """ If the debug is set to True, this will exclude any field marked `hide_from_debug`
            from the resulting send package.
        """
        record = []
        for field in self._fields:
            if debug and field.hide_from_debug:
                record.append('******')
            else:
                record.append(self[field.name])
        return record

    def dump(self):
        serialized = self.serializer.dumps(self.package(debug=True))
        s = u"JSON({})={}".format(self.code_name,serialized)
        s += u"\n--[{}]----------------------------\n".format(self.code_name)
        for field in self._fields:
            if field.hide_from_debug:
                s += u'{}: ******\n'.format(field.name)
            else:
                s += u'{}: {}\n'.format(
                              field.name,
                              self[field.name]
                          )
        return s

    def as_str(self):
        return self.serializer.dumps(self.package())

    def get(self, k, default=None):
        """ Works like dict's get. Seeks out the attribute value and
            return if found, if not, returns none
        """
        try:
            return self[k]
        except AttributeError:
            return default

    def set(self, k, v):
        """ Works like dict's set. An attribute to the provided value
        """
        self[k] = v 

    def __getitem__(self,k):
        return getattr(self,k)

    def __setitem__(self,k,v):
        return setattr(self,k,v)

    def __str__(self):
        return self.serializer.dumps(self.package())

    def __eq__(self,other):

        # Compare instance to integer (using integer WAMP message codes)
        if isinstance(other,six.integer_types):
            return self.code == other

        # Comparing instance to class
        if isinstance(other, type):
            return type(self) == other

        return self == other

    def __ne__(self,other):
        # Compare instance to integer (using integer WAMP message codes)
        if isinstance(other,six.integer_types):
            return self.code != other

        # Comparing instance to class
        if isinstance(other, type):
            return type(self) != other

        return self != other

##############################################################
# Black magic screwiness
# Finalizes the creation of the appropriate objects
# Creates the requisite Classe and Constants for message handling.
##############################################################
module = sys.modules[__name__]
for k,v in MESSAGE_TYPES.items():

    # Create the new class
    new_class = type(k, (WampMessage,), {})
    fields = MESSAGE_TYPES[k]
    new_class._fields = fields
    new_class.code_name = k
    setattr(module, k, new_class)

    # Create the constant
    code_field = fields[0]
    code_id = code_field.default_value()
    setattr(module, "WAMP_"+k, code_id)

    MESSAGE_CLASS_LOOKUP[code_id] = new_class
    MESSAGE_NAME_LOOKUP[code_id] = k



