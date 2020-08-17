
STATE_DISCONNECTED = 0
STATE_CONNECTING = 1
STATE_WEBSOCKET_CONNECTED = 3
STATE_AUTHENTICATING = 4
STATE_CONNECTED = 2

REGISTERED_CALL_URI = 0
REGISTERED_CALL_CALLBACK = 1
SUBSCRIPTION_TOPIC = 0
SUBSCRIPTION_CALLBACK = 1

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
