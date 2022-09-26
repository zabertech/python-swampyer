
STATE_DISCONNECTED = 0
STATE_CONNECTING = 1
STATE_WEBSOCKET_CONNECTED = 3
STATE_AUTHENTICATING = 4
STATE_CONNECTED = 2

REGISTERED_CALL_URI = 0
REGISTERED_CALL_CALLBACK = 1
REGISTERED_CALL_QUEUE_NAME = 2
SUBSCRIPTION_TOPIC = 0
SUBSCRIPTION_CALLBACK = 1
SUBSCRIPTION_QUEUE_NAME= 2

TRANSPORT_REGISTRY = {}

SERIALIZERS = ['json','msgpack','cbor','ubjson','flatbuffers']
SERIALIZERS_BLACKLIST = ['ubjson','flatbuffers']
SERIALIZER_REGISTRY = {}

RAWSOCKET_HANDSHAKE_ERRORS = {
    0: 'illegal (must not be used)',
    1: 'serializer unsupported',
    2: 'maximum message length unacceptable',
    3: 'use of reserved bits (unsupported feature)',
    4: 'maximum connection count reached',
}

RAWSOCKET_MESSAGE_TYPE_REGULAR = 0
RAWSOCKET_MESSAGE_TYPE_PING = 1
RAWSOCKET_MESSAGE_TYPE_PONG = 2


EV_INIT = 1
EV_EXIT = 2
EV_MAX_UPDATED = 3


try:
    from importlib.metadata import version

# This is to support python <=3.8 since they don't have importlib.metadata
except ModuleNotFoundError:
    import pkg_resources
    def version(name):
        return pkg_resources.get_distribution(name).version

