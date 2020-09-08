import os
import re
import ssl
import stat
import time
import struct

import socket
import websocket
import traceback

from .common import *
from .utils import logger
from .exceptions import *

def register_serializer(code):
    def register(klass):
        global SERIALIZER_REGISTRY
        SERIALIZER_REGISTRY[code] = klass
        return klass
    return register

class Serializer(object):
    # Used to indicate if this is a binary protocol (or not)
    binary = None

@register_serializer('json')
class JSONSerializer(Serializer):
    binary = False

    def __init__(self):
        self.json = __import__('json')

        json_module = self.json
        class WampJSONEncoder(json_module.JSONEncoder):
            """ To handle types not typically handled by JSON

                This currently just handles Decimal values and turns them
                into floats. A bit nasty but lets us continue with work
                without making nasty customizations to WAMP JSON
            """
            def default(self, obj):
                if isinstance(obj, decimal.Decimal):
                    return float(obj)
                return json_module.JSONEncoder.default(self, obj)
        self.json_encoder = WampJSONEncoder


    def dumps(self,data):
        return self.json.dumps(data, cls=self.json_encoder)

    def loads(self,data):
        return self.json.loads(data)

@register_serializer('cbor')
class CBORSerializer(Serializer):
    binary = True

    def __init__(self):
        self.cbor = __import__('cbor')
        cbor_module = self.cbor

    def dumps(self,data):
        return self.cbor.dumps(data)

    def loads(self,data):
        return self.cbor.loads(data)


@register_serializer('msgpack')
class MsgPackSerializer(Serializer):
    binary = True

    def __init__(self):
        self.msgpack = __import__('msgpack')
        msgpack_module = self.msgpack

    def dumps(self,data):
        return self.msgpack.dumps(data)

    def loads(self,data):
        return self.msgpack.loads(data)



def available_serializers():
    """ Returns a list of the current available serializers on the system
    """
    serializers = []

    for serializer in SERIALIZER_REGISTRY.keys():
        if serializer in SERIALIZERS_BLACKLIST:
            continue
        try:
            __import__(serializer)
            serializers.append(serializer)
        except Exception:
            pass

    if not serializers:
        raise ExFatalError('Unable to find a serializer on the system that imports!')

    return serializers

def load_serializer(serializer_code):
    if serializer_code not in SERIALIZER_REGISTRY:
        raise ExFatalError("Unknown serializer '{}' requested".format(serializer_code))
    if serializer_code in SERIALIZERS_BLACKLIST:
        raise ExFatalError("Serializer '{}' is not supported".format(serializer_code))

    return SERIALIZER_REGISTRY[serializer_code]()
