import os
import re
import ssl
import stat
import time
import struct
import decimal

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

    @classmethod
    def available(cls):
        return True


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
                elif isinstance(obj, memoryview):
                    return self.default(bytes(obj))
                elif isinstance(obj, bytes):
                    return obj.decode()

                return json_module.JSONEncoder.default(self, obj)
        self.json_encoder = WampJSONEncoder

    @classmethod
    def available(cls):
        __import__('json')
        return True

    def dumps(self,data):
        return self.json.dumps(data, cls=self.json_encoder)

    def loads(self,data):
        return self.json.loads(data)

@register_serializer('cbor')
class CBORSerializer(Serializer):
    binary = True

    @classmethod
    def available(cls):
        try:
            __import__('cbor2')
        except:
            __import__('cbor')
        return True

    def __init__(self):
        try:
            self.cbor = __import__('cbor2')
        except:
            try:
                self.cbor = __import__('cbor')
            except:
                pass
        cbor_module = self.cbor

    def dumps(self,data):
        return self.cbor.dumps(data)

    def loads(self,data):
        return self.cbor.loads(data)


@register_serializer('msgpack')
class MsgPackSerializer(Serializer):
    binary = True

    @classmethod
    def available(cls):
        __import__('msgpack')
        return True

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

    for serializer_name, serializer in SERIALIZER_REGISTRY.items():
        if serializer_name in SERIALIZERS_BLACKLIST:
            continue
        try:
            serializer.available()
            serializers.append(serializer_name)
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
