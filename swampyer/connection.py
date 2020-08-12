import re
import ssl
import time

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


class UnixsocketConnection(Connection):
    pass


def get_socket_connection(url, **options):
    m = re.search(r'(ws|wss|unix)://([\w\.]+)(:?:(\d+))?',url)
    if not m:
        raise ExWAMPConnectionError("Invalid format for URL: '{}'".format(url))

    protocol = m.group(1).lower()

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
