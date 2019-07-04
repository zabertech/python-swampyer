from __future__ import unicode_literals

import re
import io
import json
import time
import threading
import six
import ssl
from six.moves import queue

import websocket
from .messages import *
from .utils import logger
from .exceptions import *

STATE_DISCONNECTED = 0
STATE_CONNECTING = 1
STATE_WEBSOCKET_CONNECTED = 3
STATE_AUTHENTICATING = 4
STATE_CONNECTED = 2

REGISTERED_CALL_URI = 0
REGISTERED_CALL_CALLBACK = 1
SUBSCRIPTION_TOPIC = 0
SUBSCRIPTION_CALLBACK = 1

class WampInvokeWrapper(threading.Thread):
    """ Used to put invoke requests on a separate thread
        so we can make WAMP requests while in a WAMP request
    """
    def __init__(self,client,handler,message):
        super(WampInvokeWrapper,self).__init__()
        self.client = client
        self.handler = handler
        self.message = message

    def run(self):
        message = self.message
        req_id = message.request_id

        try:
            result = self.handler(
                message,
                *(message.args),
                **(message.kwargs)
            )
            self.client.send_message(YIELD(
                request_id = req_id,
                options={},
                args=[result]
            ))
        except Exception as ex:
            error_uri = self.client.get_full_uri('error.invoke.failure')

            exargs = ["Call failed: {}".format(ex)]
            try:
                json.dumps(ex.args) # Just testing
                exargs += list(ex.args)
            except TypeError as err:
                logger.warning("Unable to serialize exception arguments: {}".format(ex))

            try:
                self.client.send_message(ERROR(
                    request_code = WAMP_INVOCATION,
                    request_id = req_id,
                    details = {},
                    error = error_uri,
                    args = exargs
                ))

            # We might fail when we try to send an error message back to the
            # server (should we have disconnected)
            except Exception as ex:
                logger.error("ERROR attempting to send error message: {}".format(ex))

class WampSubscriptionWrapper(threading.Thread):
    """ Used to put invoke requests on a separate thread
        so we can make WAMP requests while in a WAMP request
    """
    def __init__(self,client,handler,event):
        super(WampSubscriptionWrapper,self).__init__()
        self.client = client
        self.handler = handler
        self.event = event

    def run(self):
        event = self.event
        self.handler(
            event,
            *(event.args),
            **(event.kwargs)
        )

class WAMPClient(threading.Thread):
    ws = None
    url = None
    uri_base = None
    realm = None
    agent = None
    authid = None
    authmethods = None
    timeout = None
    sslopt = None
    sockopt = None

    auto_reconnect = True

    session_id = None
    peer = None

    _subscriptions = None
    _registered_calls = None
    _request_loop_notify_restart = None
    _requests_pending = None
    _request_disconnect = None
    _request_shutdown = False
    _loop_timeout = 0.1
    _state = STATE_DISCONNECTED

    def __init__(
                self,
                url='ws://localhost:8080',
                realm='realm1',
                agent='python-swampyer-1.0',
                uri_base='',
                authmethods=None,
                authid=None,
                timeout=10,
                auto_reconnect=1,
                sslopt=None,
                sockopt=None,
                ):

        self._state = STATE_DISCONNECTED

        super(WAMPClient,self).__init__()
        self.daemon = True
        self._request_loop_notify_restart = threading.Condition()
        if auto_reconnect == True:
            auto_reconnect = 1
        self.configure(
            url = url,
            uri_base = uri_base,
            realm = realm,
            agent = agent,
            timeout = timeout,
            authid = authid,
            authmethods = authmethods,
            auto_reconnect = auto_reconnect,
            sslopt = sslopt,
            sockopt = sockopt,
        )

    def get_full_uri(self,uri):
        """ Returns the full URI with prefix attached
        """
        if self.uri_base:
            return self.uri_base + '.' + uri
        return uri

    def connect(self,soft_reset=False,**options):
        """ This just creates the websocket connection
        """
        self._state = STATE_CONNECTING
        logger.debug("About to connect to {}".format(self.url))

        m = re.search('(ws+)://([\w\.]+)(:?:(\d+))?',self.url)

        options['subprotocols'] = ['wamp.2.json']
        options['enable_multithread'] = True
        options.setdefault('timeout',self._loop_timeout)

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
                if self.sslopt:
                    options.setdefault('sslopt',self.sslopt)

                # By default if no settings are chosen we apply
                # the looser traditional policy (makes life less
                # secure but less excruciating on windows)
                if options.get('sslopt') is None:
                    options['sslopt'] = {
                        "cert_reqs":ssl.CERT_NONE,
                        "check_hostname": False
                    }

                if self.sockopt:
                    options.setdefault('sockopt',self.sockopt)

                self.ws = websocket.create_connection(
                                self.url,
                                **options
                            )
                self.handle_connect()
            except Exception as ex:
                if self.auto_reconnect:
                    logger.debug(
                        "Error connecting to {url}. Reconnection attempt in {retry} second(s). {err}".format(
                            url=self.url,
                            retry=self.auto_reconnect,
                            err=ex
                        )
                    )
                    time.sleep(self.auto_reconnect)
                    continue
                else:
                    raise
            break

        logger.debug("Connected to {}".format(self.url))
        if not soft_reset:
            self._subscriptions    = {}
            self._registered_calls = {}
        self._requests_pending = {}
        self._state = STATE_WEBSOCKET_CONNECTED

        # notify the threading.Conditional that restart can happen
        self._request_loop_notify_restart.acquire()
        self._request_loop_notify_restart.notify()
        self._request_loop_notify_restart.release()

    def is_disconnected(self):
        """ returns a true value if the connection is currently dead
        """
        return ( self._state == STATE_DISCONNECTED )

    def is_connected(self):
        """ returns a true value if the connection is currently active
        """
        return ( self._state == STATE_CONNECTED )

    def configure(self, **kwargs):
        for k in ('url','uri_base','realm',
                  'agent','timeout','authmethods', 'authid',
                  'auto_reconnect', 'sslopt', 'sockopt'):
            if k in kwargs:
                setattr(self,k,kwargs[k])


    def handle_challenge(self,data):
        """ Executed when the server requests additional
            authentication
        """
        raise NotImplemented("Received Challenge but authentication not possible. Need to subclass 'handle_challenge'?")

    def handle_connect(self):
        """ When websocket has initially connected
        """
        pass

    def handle_join(self,details):

        # Then rebind all the registrations and callbacks
        # if there's a need
        to_register = self._registered_calls
        self._registered_calls = {}
        for uri, callback in to_register.values():
            self.register(uri,callback)

        to_subscribe = self._subscriptions
        self._subscriptions = {}
        for uri, callback in to_subscribe.values():
            self.subscribe(uri,callback)

    def handle_leave(self):
        pass

    def handle_disconnect(self):
        pass

    def hello(self,details=None):
        """ Say hello to the server and wait for the welcome
            message before proceeding
        """
        self._welcome_queue = queue.Queue()

        if details is None:
            details = {}
        if self.authid:
            details.setdefault('authid', self.authid)
        details.setdefault('agent', 'swampyer-1.0')
        details.setdefault('authmethods', self.authmethods or ['anonymous'])
        details.setdefault('roles', {
                                        'subscriber': {},
                                        'publisher': {},
                                        'caller': {},
                                        'callee': {},
                                    })
        self._state = STATE_AUTHENTICATING
        self.send_message(HELLO(
                                realm = self.realm,
                                details = details
                            ))

        # Wait till we get a welcome message
        try:
            message = self._welcome_queue.get(block=True,timeout=self.timeout)
        except Exception as ex:
            raise ExWelcomeTimeout("Timed out waiting for WELCOME response")
        if message == WAMP_ABORT:
            raise ExAbort("Received abort when trying to connect: {}".format(
                    message.details.get('message',
                      message.reason)))
        self.session_id = message.session_id
        self.peer = message
        self._state = STATE_CONNECTED

        # And hook register/subscribe to anything that's required
        self.handle_join(message)

    def call(self, uri, *args, **kwargs ):
        """ Sends a RPC request to the WAMP server
        """
        if self._state == STATE_DISCONNECTED:
            raise Exception("WAMP is currently disconnected!")
        options = {
            'disclose_me': True
        }
        uri = self.get_full_uri(uri)
        message = self.send_and_await_response(CALL(
                      options=options,
                      procedure=uri,
                      args=args,
                      kwargs=kwargs
                    ))

        if message == WAMP_RESULT:
            return message.args[0]

        if message == WAMP_ERROR:
            if message.args:
                err = message.args
            else:
                err = [message.error]
            raise ExInvocationError(*err)

        return message

    def send_message(self,message):
        """ Send awamp message to the server. We don't wait
            for a response here. Just fire out a message
        """
        if self._state == STATE_DISCONNECTED:
            raise Exception("WAMP is currently disconnected!")
        message = message.as_str()
        logger.debug("SND>: {}".format(message))
        if not self.ws:
            raise Exception("WAMP is currently disconnected!")
        self.ws.send(message)

    def send_and_await_response(self,request):
        """ Used by most things. Sends out a request then awaits a response
            keyed by the request_id
        """
        if self._state == STATE_DISCONNECTED:
            raise Exception("WAMP is currently disconnected!")
        wait_queue = queue.Queue()
        request_id = request.request_id
        self._requests_pending[request_id] = wait_queue;
        self.send_message(request)
        try:
            return wait_queue.get(block=True,timeout=self.timeout)
        except Exception as ex:
            raise Exception("Did not receive a response!")

    def dispatch_to_awaiting(self,result):
        """ Send dat ato the appropriate queues
        """

        # If we are awaiting to login, then we might also get
        # an abort message. Handle that here....
        if self._state == STATE_AUTHENTICATING:
            # If the authentication message is something unexpected,
            # we'll just ignore it for now
            if result == WAMP_ABORT \
               or result == WAMP_WELCOME \
               or result == WAMP_GOODBYE:
                self._welcome_queue.put(result)
            return

        try:
            request_id = result.request_id
            if request_id in self._requests_pending:
                self._requests_pending[request_id].put(result)
                del self._requests_pending[request_id]
        except:
            raise Exception("Response does not have a request id. Do not know who to send data to. Data: {} ".format(result.dump()))

    def handle_welcome(self, welcome):
        """ Hey cool, we were told we can access the server!
        """
        self._welcome_queue.put(welcome)

    def handle_result(self, result):
        """ Dispatch the result back to the appropriate awaiter
        """
        self.dispatch_to_awaiting(result)

    def handle_goodbye(self, goodbye):
        """ Dispatch the result back to the appropriate awaiter
        """
        pass

    def handle_result(self, result):
        """ Dispatch the result back to the appropriate awaiter
        """
        self.dispatch_to_awaiting(result)

    def handle_subscribed(self, result):
        """ Handle the successful subscription
        """
        self.dispatch_to_awaiting(result)

    def handle_registered(self, result):
        """ Handle the request registration
        """
        self.dispatch_to_awaiting(result)

    def handle_error(self, error):
        """ OOops! An error occurred
        """
        self.dispatch_to_awaiting(error)

    def handle_abort(self, reason):
        """ We're out?
        """
        self._welcome_queue.put(reason)
        self.close()
        self.disconnect()

    def handle_invocation(self, message):
        """ Passes the invocation request to the appropriate
            callback.
        """
        req_id = message.request_id
        reg_id = message.registration_id
        if reg_id in self._registered_calls:
            handler = self._registered_calls[reg_id][REGISTERED_CALL_CALLBACK]
            invoke = WampInvokeWrapper(self,handler,message)
            invoke.start()
        else:
            error_uri = self.get_full_uri('error.unknown.uri')
            self.send_message(ERROR(
                request_code = WAMP_INVOCATION,
                request_id = req_id,
                details = {},
                error =error_uri
            ))

    def handle_event(self, event):
        """ Send the event to the subclass or simply reject
        """
        subscription_id = event.subscription_id
        if subscription_id in self._subscriptions:
            # FIXME: [1] should be a constant
            handler = self._subscriptions[subscription_id][SUBSCRIPTION_CALLBACK]
            WampSubscriptionWrapper(self,handler,event).start()

    def handle_unknown(self, message):
        """ We don't know what to do with this. So we'll send it
            into the queue just in case someone wants to do something
            with it but we'll just blackhole it.
        """
        self.dispatch_to_awaiting(message)

    def subscribe(self,topic,callback=None,options=None):
        """ Subscribe to a uri for events from a publisher
        """
        full_topic = self.get_full_uri(topic)
        result = self.send_and_await_response(SUBSCRIBE(
                                    options=options or {},
                                    topic=full_topic
                                ))
        if result == WAMP_SUBSCRIBED:
            if not callback:
                callback = lambda a: None
            self._subscriptions[result.subscription_id] = [topic,callback]

    def publish(self,topic,options=None,args=None,kwargs=None):
        """ Publishes a messages to the server
        """
        topic = self.get_full_uri(topic)
        if options is None:
            options = {'acknowledge':True}
        if options.get('acknowledge'):
            request = PUBLISH(
                        options=options or {},
                        topic=topic,
                        args=args or [],
                        kwargs=kwargs or {}
                      )
            result = self.send_and_await_response(request)
            return result
        else:
            request = PUBLISH(
                        options=options or {},
                        topic=topic,
                        args=args or [],
                        kwargs=kwargs or {}
                      )
            self.send_message(request)
            return request.request_id

    def disconnect(self):
        """ Disconnect from the websocket and pause the process
            till we reconnect
        """
        logger.debug("Disconnecting")

        # Close off the websocket
        if self.ws:
            try:
                if self._state == STATE_CONNECTED:
                    self.handle_leave()
                    self.send_message(GOODBYE(
                          details={},
                          reason="wamp.error.system_shutdown"
                        ))
                logger.debug("Closing Websocket")
                try:
                    self.ws.close()
                except Exception as ex:
                    logger.debug("Could not close websocket connection because: {}".format(ex))
            except Exception as ex:
                logger.debug("Could not send Goodbye message because {}".format(ex))
                pass # FIXME: Maybe do better handling here
            self.ws = None

        # Cleanup the state variables. By settings this
        # we're going to be telling the main loop to stop
        # trying to read from a websocket and await a notice
        # of restart via a threading.Condition object
        self._state = STATE_DISCONNECTED

        # Send a message to all queues that we have disconnected
        # Without this, any requests that are awaiting a response
        # will block until timeout needlessly
        for request_id, request_queue in self._requests_pending.items():
            request_queue.put(GOODBYE(
                          details={},
                          reason="wamp.error.system_shutdown"
                        ))
        self._requests_pending = {}
        self.handle_disconnect()

    def shutdown(self):
        """ Request the system to shutdown the main loop and shutdown the system
            This is a one-way trip! Reconnecting requires a new connection
            to be made!
        """
        self._request_shutdown = True
        for i in range(100):
            if self._state == STATE_DISCONNECTED:
                break
            time.sleep(0.1)

    def start(self):
        """ Initialize websockets, say hello, and start listening for events
        """
        self.connect()
        if not self.isAlive():
            super(WAMPClient,self).start()
        self.hello()
        return self

    def reconnect(self):
        """ Attempt to reconnect to the WAMP server. Thia also assumes that
            the main loop is still running
        """

        # Reset the connection
        self.connect(soft_reset=True)

        # And hello hello
        self.hello()

        return self

    def register(self,uri,callback,details=None):
        full_uri = self.get_full_uri(uri)
        result = self.send_and_await_response(REGISTER(
                      details=details or {},
                      procedure=full_uri
                  ))
        if result == WAMP_REGISTERED:
            self._registered_calls[result.registration_id] = [ uri, callback ]
        return result

    def run(self):
        """ Waits and receives messages from the server. This
            function somewhat needs to block so is executed in its
            own thread until self._request_shutdown is called.
        """
        while not self._request_shutdown:

            # Find out if we have any data pending from the
            # server
            try:

                # If we've been asked to stop running the
                # request loop. We'll just sit and wait
                # till we get asked to run again
                if self._state not in [STATE_AUTHENTICATING,STATE_WEBSOCKET_CONNECTED,STATE_CONNECTED]:
                    self._request_loop_notify_restart.acquire()
                    self._request_loop_notify_restart.wait(self._loop_timeout)
                    self._request_loop_notify_restart.release()
                    continue

                # If we don't have a websocket defined.
                # we don't go further either
                elif not self.ws:
                    logger.debug("No longer have a websocket. Marking disconnected")
                    self._state = STATE_DISCONNECTED
                    continue

                # Okay, we think we're okay so let's try and read some data
                data = self.ws.recv()
            except io.BlockingIOError:
                continue
            except websocket.WebSocketTimeoutException:
                continue
            except websocket.WebSocketConnectionClosedException as ex:
                logger.debug("WebSocketConnectionClosedException: Requesting disconnect:".format(ex))
                self.disconnect()

                # If the server disconnected, let's try and reconnect
                # back to the service after a random few seconds
                if self.auto_reconnect:
                    # As doing a reconnect would block and would then
                    # prevent us from ticking the websoocket, we'll
                    # go into a subthread to deal with the reconnection
                    def reconnect():
                        self.reconnect()
                    t = threading.Thread(target=reconnect)
                    t.start()

                    # FIXME: need to randomly wait
                    time.sleep(1)
                    if not data: continue
            except Exception as ex:
                logger.error("ERROR in main loop: {}".format(ex))
                continue

            try:
                logger.debug("<RCV: {}".format(data))
                message = WampMessage.loads(data)
                logger.debug("<RCV: {}".format(message.dump()))
                try:
                    code_name = message.code_name.lower()
                    handler_name = "handle_"+code_name
                    handler_function = getattr(self,handler_name)
                    handler_function(message)
                except AttributeError as ex:
                    self.handle_unknown(message)
            except Exception as ex:
                logger.error("ERROR in main loop: {}".format(ex))

class WAMPClientTicket(WAMPClient):
    username = None
    password = None

    def __init__(
                self,
                password=None,
                username=None,
                **kwargs
                ):

        if not kwargs.get('authmethods'):
            kwargs['authmethods'] = ['ticket']
        super(WAMPClientTicket,self).__init__(**kwargs)
        self.daemon = True

        self.configure(
            password = password,
            username = username,
            **kwargs
        )

    def configure(self, **kwargs):
        # Just alias username to make things "easier"
        if 'username' in kwargs:
            kwargs.setdefault('authid',kwargs['username'])

        super(WAMPClientTicket,self).configure(**kwargs)
        for k in ('password',):
            if k in kwargs:
                setattr(self,k,kwargs[k])

    def handle_challenge(self,data):
        """ Executed when the server requests additional
            authentication
        """
        # Send challenge response
        self.send_message(AUTHENTICATE(
            signature = self.password,
            extra = {}
        ))
