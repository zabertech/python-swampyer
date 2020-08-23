import io
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
from .messages import *
from .utils import logger
from .exceptions import *
from .serializers import *

def register_transport(code):
    def register(klass):
        global TRANSPORT_REGISTRY
        TRANSPORT_REGISTRY[code] = klass
        return klass
    return register


class Transport(object):
    def __init__(self, url, serializers=None, **options):
        self.url = url
        self.socket = None
        if not serializers:
            serializers = available_serializers()
        self.serializers = serializers
        self.init(**options)

    def init(self, **options):
        pass

    def connect(self, **options):
        raise ExNotImplemented("connect is not implemented")

    def settimeout(self, timeout):
        raise ExNotImplemented("settimeout is not implemented")

    def ping(self, last_ping_time):
        raise ExNotImplemented("ping is not implemented")

    def send(self, payload):
        raise ExNotImplemented("send is not implemented")

    def send_message(self, message):
        """ Used by the client to send a message object. This will
            allow us to intercept and serialize to the appropriate
            format before sending it on.
        """
        payload = self.serializer.dumps(message.package())
        self.send(payload)

    def close(self):
        raise ExNotImplemented("close is not implemented")

    def recv_data(self, control_frame=True):
        raise ExNotImplemented("recv_data is not implemented")

    def next(self):
        raise ExNotImplemented("next is not implemented")

@register_transport('ws')
@register_transport('wss')
class WebsocketTransport(Transport):

    loop_timeout = 1
    protocol = 'ws'
    ssl_origin =None
    sslopt = None
    subprotocols = None
    fire_cont_frame = False
    skip_utf8_validation = False

    def init(self, **options):

        self.subprotocols = []
        for serializer_code in self.serializers:
            self.subprotocols.append('wamp.2.{}'.format(serializer_code))

        m = re.search(r'(ws|wss)://([\w\.]+)(:?:(\d+))?',self.url)
        if not m:
            raise ExTransportParseError('Require ws://path or wss:// syntax for Websocket')
        self.protocol = m.group(1).lower()

        if self.protocol == 'wss':
            origin_port = ':'+m.group(4) if m.group(4) else ''
            self.ssl_origin = 'https://{}{}'.format(m.group(2),origin_port)

        # By default if no settings are chosen we apply
        # the looser traditional policy (makes life less
        # secure but less excruciating on windows)
        self.sslopt = options.get('sslopt', {
                "cert_reqs":ssl.CERT_NONE,
                "check_hostname": False
            })

        self.loop_timeout = options.get('loop_timeout')
        self.fire_cont_frame = options.get('fire_cont_frame',False)
        self.skip_utf8_validation = options.get('skip_utf8_validation',False)

    def connect(self, **options):
        # Handle the weird issue in websocket that the origin
        # port will be always http://host:port even though connection is
        # wss. This causes some origin issues with demo.crossbar.io demo
        # so we ensure we use http or https appropriately depending on the
        # ws or wss protocol

        options.setdefault('sslopt',self.sslopt)
        options.setdefault('subprotocols',self.subprotocols)

        self.socket = websocket.WebSocket(
                            fire_cont_frame=options.pop(
                                  "fire_cont_frame", self.fire_cont_frame),
                            skip_utf8_validation=options.pop(
                                  "skip_utf8_validation", self.skip_utf8_validation),
                            enable_multithread=True,
                            **options)
        self.socket.settimeout(options.get('loop_timeout',self.loop_timeout))
        self.socket.connect(self.url, **options)

        serializer_code = self.socket.subprotocol[len('wamp.2.'):]
        self.serializer = load_serializer(serializer_code)

    def settimeout(self, timeout):
        return self.socket.settimeout(timeout)

    def ping(self, last_ping_time):
        return self.socket.ping(last_ping_time)

    def send(self, payload):
        try:
            if self.serializer.binary:
                self.socket.send_binary(payload)
            else:
                if isinstance(payload, (bytes, bytearray)):
                    payload = payload.encode('utf8')
                self.socket.send(payload)
        except websocket.WebSocketConnectionClosedException:
            raise ExWAMPConnectionError("WAMP is currently disconnected!")

    def close(self):
        return self.socket.close()

    def recv_data(self, control_frame=True):
        return self.socket.recv_data(control_frame)

    def next(self):
        """ Returns the next  buffer element
        """
        try:
            opcode, data = self.socket.recv_data(control_frame=True)

            if opcode == websocket.ABNF.OPCODE_TEXT:
                # Try to decode the data as a utf-8 string. Replace any inconvertible characters
                # to the unicode `\uFFFD` character
                data = data.decode('utf-8', 'replace')
                return self.serializer.loads(data)

            if opcode == websocket.ABNF.OPCODE_BINARY:
                return self.serializer.loads(data)

            if opcode == websocket.ABNF.OPCODE_PONG:
                duration = time.time() - float(data)
                self._last_pong_time = time.time()
                data = None
                opcode = None
                logger.debug('Received websocket ping response in %s seconds', round(duration, 3))
                return
            
            if opcode not in (websocket.ABNF.OPCODE_TEXT, websocket.ABNF.OPCODE_BINARY):
                return
        except io.BlockingIOError:
            return
        except websocket.WebSocketTimeoutException:
            return
        except websocket.WebSocketConnectionClosedException as ex:
            raise ExWAMPConnectionError(ex)
        except (ExWAMPConnectionError, socket.error) as ex:
            raise 


class RawsocketTransport(Transport):
    """
    Raw Socket transport is detailed here:

    https://github.com/wamp-proto/wamp-proto/blob/master/rfc/text/advanced/ap_transport_rawsocket.md
    """

    buffer_size = 0xf
    serializer = None
    server_buffer_size = 0

    def create_socket(self, *args, **kwargs):
        raise ExNotImplementedError('create_socket has not been implemented')

    def perform_handshake(self,serializer_code):
        """ Negotiates the serialization format 
        """

        # As noted in https://github.com/wamp-proto/wamp-proto/blob/master/rfc/text/advanced/ap_transport_rawsocket.md
        #
        # Client sends 4 bytes:
        #
        # Byte 1: 0x7F
        # 
				# Byte 2: High nybble: Length, Low nybble: Serializer
        #       Length: Maximum message length client wishes to receive
        #               0: 2**9 octets
        #               1: 2**10 octets
        #               ...
        #               15: 2**24 octets
        # 
				#       Serializer: Numeric constants to identify what to use
        #               1: JSON
        #               2: MessagePack
        #               3 - 15: Reserved
        try:
            serializer = SERIALIZERS.index(serializer_code) + 1
        except ValueError:
            raise ExWAMPConnectionError("Unknown serializer '{}' requested".format(serializer_code))
        client_handshake = struct.pack(
                                '!BBBB',
                                0x7f,
                                self.buffer_size << 4 | serializer,
                                0, 0 # Reserved
                            )

        self.socket.send(client_handshake)

				# Server will then respond with 4 bytes
        server_magic = self.socket.recv(1)
        if server_magic != b'\x7f':
            raise ExWAMPConnectionError("Server is not speaking RawSocket. Received '{}' instead!".format(server_magic))

        # Then next 3 bytes
        server_handshake = struct.unpack('!B',self.socket.recv(1))[0]
        server_serializer = server_handshake & 0x0f
        server_buffer_size = server_handshake >> 4 | 0x0f

        # If serializer is 0x00, there was an error
        if server_serializer == 0x00:
            raise ExWAMPConnectionError(RAWSOCKET_HANDSHAKE_ERRORS[server_buffer_size])

        # Otherwise, we're still good and can parse things out
        if server_serializer != serializer:
            raise ExWAMPConnectionError(
                "Server didn't want to use the same serializer! Got '{server_serializer}' but expected '{serializer}'".format(
                    server_serializer=server_serializer,
                    serializer=self.serializer,
                ))

        # Serializer okay'd so let's use it
        self.serializer = load_serializer(serializer_code)

        self.server_buffer_size = 2**(9+server_buffer_size)

        # And skip the reserved bytes
        server_reserved = self.socket.recv(2)

        return True

    def connect(self, **options):
        self.socket = self.create_socket()
        for serializer_code in self.serializers:
            if self.perform_handshake(serializer_code):
                break

    def settimeout(self, timeout):
        return self.socket.settimeout(timeout)

    def ping(self, last_ping_time):
        # We don't do anything here since crossbar doesn't support ping/pong
        # on raw sockets. Instead it treats the 0 byte as part of the length
        # and thus explodes
        # https://github.com/crossbario/crossbar/issues/381
        #epoch_time = time.time()
        #epoch_buf = struct.pack('!d', epoch_time)
        #self.send(epoch_buf, RAWSOCKET_MESSAGE_TYPE_PING)
        return True

    def send(self, payload, message_type=RAWSOCKET_MESSAGE_TYPE_REGULAR):
        if not isinstance(payload, (bytes, bytearray)):
            payload = payload.encode('utf8')

        header = struct.pack('!B',message_type)

        # Python doesn't do 24bit ints so we tweak here
        length = struct.pack('!I',len(payload))[1:]

        send_data = header + length + payload
        return self.socket.send(send_data)

    def close(self):
        return self.socket.close()

    def recv_data(self, control_frame=True):
        first_byte = self.socket.recv(1)
        if first_byte is None or len(first_byte) == 0:
            return
        message_preamble = struct.unpack('!B',first_byte)[0]
        message_contents = self.socket.recv(3)

        magic = message_preamble & 0b11111000
        if magic != 0:
            raise ExMessageCorrupt("Received unexpected bits in message preamble")

        # The last three bits of the preamble determine the message
        # type
        # 0: regular WAMP message
        # 1: PING
        # 2: PONG
        # 3-7: reserved
        message_type = message_preamble & 0b00000111

        # If it's a regular message, the next 3 bytes denote the length of the upcoming
        # serialized data
        if message_type == RAWSOCKET_MESSAGE_TYPE_REGULAR:
            message_length = struct.unpack('!I', message_contents + b'\0')[0]
            message_payload = self.socket.recv(message_length)
            return message_payload

        # We don't do anything here since crossbar doesn't support ping/pong
        # on raw sockets. Instead it treats the 0 byte as part of the length
        # and thus explodes
        # https://github.com/crossbario/crossbar/issues/381
        # So until crossbar does support ping/pong, we'll leave this commented out
        #
        #elif message_type == RAWSOCKET_MESSAGE_TYPE_PING:
        #    message_length = struct.unpack('!I', message_contents + b'\0')[0]
        #    message_payload = self.socket.recv(message_length)
        #    self.send(message_payload,RAWSOCKET_MESSAGE_TYPE_PONG)
        #    return
        # elif message_type == RAWSOCKET_MESSAGE_TYPE_PONG:
        #    return

    def next(self):
        """ Returns the next  buffer element
        """
        message_payload = self.recv_data()
        if not message_payload: return
        return self.serializer.loads(message_payload)

@register_transport('unix')
class UnixsocketTransport(RawsocketTransport):

    socket_path = None

    def init(self, **options):
        m = re.search(r'unix://(.*)',self.url)
        if not m:
            raise ExTransportParseError('Require unix://path syntax for UnixsocketConnections')

        # Check if the path exists and is a socket
        socket_path = m.group(1)
        if not os.path.exists(socket_path):
            raise ExWAMPConnectionError("Unix Socket '{}' does not exist".format(socket_path))
        socket_mode = os.stat(socket_path).st_mode
        if not stat.S_ISSOCK(socket_mode):
            raise ExWAMPConnectionError("Path '{}' is not a socket!".format(socket_path))
        self.socket_path = socket_path

    def create_socket(self):
        # TODO: Look into SOCK_DGRAM
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(self.socket_path)
        return sock

@register_transport('tcpip')
class TcpipsocketTransport(RawsocketTransport):
    socket_path = None
    host = None
    port = None

    def init(self, **options):
        m = re.search(r'tcpip://([\w\.]+):(\d+)',self.url)
        if not m:
            raise ExTransportParseError('Require tcpip://host:port syntax for Rawsocket Connection')
        self.host = m.group(1)
        self.port = int(m.group(2))

    def create_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.host, self.port))
        return sock


def get_transport(url, **options):
    ( protocol, junk ) = url.lower().split(':',1)
    if not protocol:
        raise ExWAMPConnectionError("Unknown transport protocol for URL: '{}'".format(protocol))

    if protocol not in TRANSPORT_REGISTRY:
        raise ExWAMPConnectionError("Transport protocol '{}' not known".format(protocol))
        
    return TRANSPORT_REGISTRY[protocol](url, **options)


