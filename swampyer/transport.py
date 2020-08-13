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

class Connection(object):
    def __init__(self, url, **options):
        self.url = url
        self.socket = None

    def connect(self, url, **options):
        raise ExNotImplemented("connect is not implemented")

    def settimeout(self, timeout):
        raise ExNotImplemented("settimeout is not implemented")

    def ping(self, last_ping_time):
        raise ExNotImplemented("ping is not implemented")

    def send(self, payload):
        raise ExNotImplemented("send is not implemented")

    def close(self):
        raise ExNotImplemented("close is not implemented")

    def recv_data(self, control_frame=True):
        raise ExNotImplemented("recv_data is not implemented")

class WebsocketConnection(Connection):

    def connect( self, **options ):

        options['subprotocols'] = ['wamp.2.json']
        m = re.search(r'(ws|wss)://([\w\.]+)(:?:(\d+))?',self.url)

        auto_reconnect = options.get('auto_reconnect',1)

        # Handle the weird issue in websocket that the origin
        # port will be always http://host:port even though connection is
        # wss. This causes some origin issues with demo.crossbar.io demo
        # so we ensure we use http or https appropriately depending on the
        # ws or wss protocol
        if m and m.group(1).lower() == 'wss':
            origin_port = ':'+m.group(4) if m.group(4) else ''
            options['origin'] = 'https://{}{}'.format(m.group(2),origin_port)

        # Attempt connection once unless it's autoreconnect in which
        # case we try and try again...
        while True:
            try:
                # By default if no settings are chosen we apply
                # the looser traditional policy (makes life less
                # secure but less excruciating on windows)
                if options.get("sslopt") is None:
                    options["sslopt"] = {
                        "cert_reqs":ssl.CERT_NONE,
                        "check_hostname": False
                    }

                self.socket = websocket.WebSocket(fire_cont_frame=options.pop("fire_cont_frame", False),
                                    skip_utf8_validation=options.pop("skip_utf8_validation", False),
                                    enable_multithread=True,
                                    **options)
                self.socket.settimeout(options['loop_timeout'])
                self.socket.connect(self.url, **options)
            except Exception as ex:
                if auto_reconnect:
                    logger.debug(
                        "Error connecting to {url}. Reconnection attempt in {retry} second(s). {err}".format(
                            url=self.url,
                            retry=auto_reconnect,
                            err=ex
                        )
                    )
                    time.sleep(auto_reconnect)
                    continue
                else:
                    raise
            break

    def settimeout(self, timeout):
        return self.socket.settimeout(timeout)

    def ping(self, last_ping_time):
        return self.socket.ping(last_ping_time)

    def send(self, payload):
        return self.socket.send(payload)

    def close(self):
        return self.socket.close()

    def recv_data(self, control_frame=True):
        return self.socket.recv_data(control_frame)

    def next(self):
        """ Returns the next  buffer element
        """
        try:
            # Okay, we think we're okay so let's try and read some data
            opcode, data = self.socket.recv_data(control_frame=True)
            if opcode == websocket.ABNF.OPCODE_TEXT:
                # Try to decode the data as a utf-8 string. Replace any inconvertible characters
                # to the unicode `\uFFFD` character
                data = data.decode('utf-8', 'replace')
                return data

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


class RawsocketConnection(Connection):
    def connect( self, url, **options ):
        options['subprotocols'] = ['wamp.2.json']
        m = re.search(r'tcpip://([\w\.]+):(\d+)',self.url)
        if not m:
            raise ExWAMPConnectionError('Require tcpip://path syntax for Rawsocket Connection')

        # Check if the path exists and is a socket
        socket_path = m.group(1)
        if not os.path.exists(socket_path):
            raise ExWAMPConnectionError('Unix Socket {} does not exist'.format(socket_path))
        socket_mode = os.stat(socket_path).st_mode
        if not stat.S_ISSOCK(mode):
            raise ExWAMPConnectionError('Path {} is not a socket!'.format(socket_path))

        auto_reconnect = options.get('auto_reconnect',1)

        # Attempt connection once unless it's autoreconnect in which
        # case we try and try again...
        while True:
            try:
                # TODO: Look into SOCK_DGRAM
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.connect( socket_path )
                self.socket = sock
            except Exception as ex:
                if auto_reconnect:
                    logger.debug(
                        "Error connecting to {url}. Reconnection attempt in {retry} second(s). {err}".format(
                            url=self.url,
                            retry=auto_reconnect,
                            err=ex
                        )
                    )
                    time.sleep(auto_reconnect)
                    continue
                else:
                    raise
            break

    def settimeout(self, timeout):
        return self.socket.settimeout(timeout)

    def ping(self, last_ping_time):
        # Unix sockets do not need a ping
        return True

    def send(self, payload):
        return self.socket.send(payload)

    def close(self):
        return self.socket.close()

    def recv_data(self, control_frame=True):
        return self.socket.recv_data(control_frame)

class RawsocketConnection(Connection):
    """
    Raw Socket transport is detailed here:

    https://github.com/wamp-proto/wamp-proto/blob/master/rfc/text/advanced/ap_transport_rawsocket.md
    """

    def connect( self, **options ):
        pass

class UnixsocketConnection(RawsocketConnection):

    buffer_size = 0xf
    serializer = RAWSOCKET_SERIALIZER_JSON
    server_buffer_size = 0

    def perform_handshake(self):
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
        client_handshake = struct.pack(
                                '!BBBB',
                                0x7f,
                                self.buffer_size << 4 | self.serializer,
                                0, 0 # Reserved
                            )

        type(client_handshake)
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
        if server_serializer != self.serializer:
            raise ExWAMPConnectionError(
                "Server didn't want to use the same serializer! Got '{server_serializer}' but expected '{serializer}'".format(
                    server_serializer=server_serializer,
                    serializer=self.serializer,
                ))
        self.server_buffer_size = 2**(9+server_buffer_size)

        # And skip the reserved bytes
        server_reserved = self.socket.recv(2)

    def connect( self, **options ):
        options['subprotocols'] = ['wamp.2.json']
        m = re.search(r'unix://(.*)',self.url)
        if not m:
            raise ExWAMPConnectionError('Require unix://path syntax for UnixsocketConnections')

        # Check if the path exists and is a socket
        socket_path = m.group(1)
        if not os.path.exists(socket_path):
            raise ExWAMPConnectionError("Unix Socket '{}' does not exist".format(socket_path))
        socket_mode = os.stat(socket_path).st_mode
        if not stat.S_ISSOCK(socket_mode):
            raise ExWAMPConnectionError("Path '{}' is not a socket!".format(socket_path))

        auto_reconnect = options.get('auto_reconnect',1)

        # Attempt connection once unless it's autoreconnect in which
        # case we try and try again...
        while True:
            try:
                # TODO: Look into SOCK_DGRAM
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.connect(socket_path)
                self.socket = sock
                self.perform_handshake()

            except Exception as ex:
                if auto_reconnect:
                    logger.debug(
                        "Error connecting to {url}. Reconnection attempt in {retry} second(s). {err}.\n{traceback}".format(
                            url=self.url,
                            retry=auto_reconnect,
                            err=ex,
                            traceback=traceback.format_exc(),
                        )
                    )
                    time.sleep(auto_reconnect)
                    continue
                else:
                    raise
            break

    def settimeout(self, timeout):
        return self.socket.settimeout(timeout)

    def ping(self, last_ping_time):
        # Unix sockets do not need a ping
        return True

    def send(self, payload):
        if not isinstance(payload, bytearray):
            payload = payload.encode('utf8')

        header = struct.pack('!B',0)

        # Python doesn't do 24bit ints so we tweak here
        length = struct.pack('!I',len(payload))[1:]

        send_data = header + length + payload
        return self.socket.send(send_data)

    def close(self):
        return self.socket.close()

    def recv_data(self, control_frame=True):
        message_preamble = struct.unpack('!B',self.socket.recv(1))[0]
        message_contents = self.socket.recv(3)

        print("message preamble", message_preamble, type(message_preamble))
        print("message contents", message_contents)
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

        elif message_type == RAWSOCKET_MESSAGE_TYPE_PING:
            raise NotImplementedError("Message type of PING not yet handled")

        elif message_type == RAWSOCKET_MESSAGE_TYPE_PONG:
            raise NotImplementedError("Message type of PONG not yet handled")

    def next(self):
        """ Returns the next  buffer element
        """
        message_preamble = struct.unpack('!B',self.socket.recv(1))[0]
        message_contents = self.socket.recv(3)

        print("message preamble", message_preamble, type(message_preamble))
        print("message contents", message_contents)
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

        elif message_type == RAWSOCKET_MESSAGE_TYPE_PING:
            raise NotImplementedError("Message type of PING not yet handled")

        elif message_type == RAWSOCKET_MESSAGE_TYPE_PONG:
            raise NotImplementedError("Message type of PONG not yet handled")


def get_socket_connection(url, **options):
    ( protocol, junk ) = url.lower().split(':',1)
    #m = re.search(r'(ws|wss|tcpip|unix).*',url)
    if not protocol:
        raise ExWAMPConnectionError("Unknown protocol for URL: '{}'".format(protocol))

    if protocol in('ws','wss'):
        socket = WebsocketConnection(url)
        socket.connect(**options)
        return socket

    elif protocol in('unix'):
        socket = UnixsocketConnection(url)
        socket.connect(**options)
        return socket

    else:
        raise ExWAMPConnectionError("Unknown URL format {}. Must be ws://, wss://, or unix://".format(url))
