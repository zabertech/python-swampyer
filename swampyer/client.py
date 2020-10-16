from __future__ import unicode_literals

import re
import io
import json
import time
import ctypes
import threading
import traceback
import six
from six.moves import queue

import socket

from .common import *
from .messages import *
from .utils import logger
from .exceptions import *
from .transport import *
from .serializers import *
from .queues import *

class WampInvokeWrapper(ConcurrencyRunner):
    """ Used to put invoke requests on a separate thread
        so we can make WAMP requests while in a WAMP request
    """
    def __init__(self,handler,message,client):
        super(WampInvokeWrapper,self).__init__(handler,message)
        self.client = client

    def handle_error(self, ex):
        error_uri = self.client.get_full_uri('error.invoke.failure')
        req_id = self.message.request_id

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


    def work(self):
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
            self.handle_error(ex)

class WampSubscriptionWrapper(ConcurrencyRunner):
    """ Used to put invoke requests on a separate thread
        so we can make WAMP requests while in a WAMP request
    """
    def __init__(self,handler,message,client):
        super(WampSubscriptionWrapper,self).__init__(handler, message)
        self.client = client

        # Alias message to event for the sake of clarity
        self.event = message

    def work(self):
        event = self.event
        self.handler(
            event,
            *(event.args),
            **(event.kwargs)
        )



class WAMPClient(threading.Thread):
    url = None
    uri_base = None
    realm = None
    agent = None
    authid = None
    authmethods = None
    timeout = None
    sslopt = None
    sockopt = None
    loop_timeout = 5
    heartbeat_timeout = 10
    ping_interval = 3

    auto_reconnect = True

    session_id = None
    peer = None

    concurrency_class = None
    concurrency_max = None
    concurrency_queue_max = None
    concurrency_configs = None
    concurrency_strict_naming = False

    _subscriptions = None
    _registered_calls = None
    _request_loop_notify_restart = None
    _requests_pending = None
    _request_disconnect = None
    _request_shutdown = False
    _state = STATE_DISCONNECTED
    _concurrency_queues = None

    _stats = None

    _last_ping_time = None
    _last_pong_time = None
    _heartbeat_thread = None
    _stop_heartbeat = False

    def __init__(
                self,
                url='ws://localhost:8080',
                realm='realm1',
                agent='python-swampyer-1.0',
                uri_base='',
                authmethods=None,
                authid=None,
                timeout=10,
                loop_timeout=5,
                heartbeat_timeout=10,
                ping_interval=3,
                auto_reconnect=1,
                sslopt=None,
                sockopt=None,
                serializers=None,
                concurrency_max=None,
                concurrency_queue_max=None,
                concurrency_class=None,
                concurrency_configs=None,
                concurrency_strict_naming=True,
                concurrency_queues=None,
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
            loop_timeout = loop_timeout,
            heartbeat_timeout = heartbeat_timeout,
            ping_interval = ping_interval,
            serializers = serializers,
            concurrency_max = concurrency_max,
            concurrency_queue_max = concurrency_queue_max,
            concurrency_class = concurrency_class,
            concurrency_configs = concurrency_configs,
            concurrency_strict_naming = concurrency_strict_naming,
        )

    def get_full_uri(self,uri):
        """ Returns the full URI with prefix attached
        """
        if self.uri_base:
            return self.uri_base + '.' + uri
        return uri

    def connect(self,soft_reset=False,**options):
        """ This just creates the transport
        """
        self._state = STATE_CONNECTING
        logger.debug("About to connect to {}".format(self.url))

        options.setdefault('sslopt',self.sslopt)
        options.setdefault('loop_timeout',self.loop_timeout)
        options.setdefault('serializers',self.serializers)

        # Attempt connection once unless it's autoreconnect in which
        # case we try and try again...
        auto_reconnect = options.get('auto_reconnect',self.auto_reconnect)
        while True:
            try:
                self.transport_connect(**options)
            except ExFatalError as ex:
                logger.debug(
                    "Fatal Error connecting to {url}. {err}.\n{traceback}".format(
                        url=self.url,
                        err=ex,
                        traceback=traceback.format_exc(),
                    )
                )
                raise

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


        logger.debug("Connected to {}".format(self.url))
        if not soft_reset:
            self._subscriptions    = {}
            self._registered_calls = {}
            self._concurrency_queues = {}
            self._stats = None

        if self._stats is None:
            self._stats = {
                'messages': 0,
                'invocations': 0,
                'calls': 0,
                'events': 0,
                'publications': 0,
                'errors': 0,
                'last_reset': time.time(),
                'reconnections': 0,
            }

            
        # Setup the invoke/subscribe concurrency handlers
        for concurrency_queue in self._concurrency_queues.values():
            concurrency_queue.reset()

        self._requests_pending = {}
        self._state = STATE_WEBSOCKET_CONNECTED


        # notify the threading.Conditional that restart can happen
        self._request_loop_notify_restart.acquire()
        self._request_loop_notify_restart.notify()
        self._request_loop_notify_restart.release()

    def start_heartbeat(self, event):
        self._last_ping_time = None
        self._last_pong_time = None
        while not event.wait(self.ping_interval) and not self._stop_heartbeat:
            self._last_ping_time = time.time()
            try:
                self.transport.ping(str(self._last_ping_time))
            except Exception as ex:
                raise ExWAMPConnectionError("Ping failed: %s", ex)
        self._stop_heartbeat = False

    def stop_heartbeat(self):
        self._stop_heartbeat = True

    def heartbeat(self):
        """ starts a new thread that sends the transport ping messages to
        the router.
        """
        self._stop_heartbeat = False
        if self.ping_interval:
            event = threading.Event()
            thread = threading.Thread(
                target=self.start_heartbeat, args=(event,))
            thread.setDaemon(True)
            thread.start()
            self.heartbeat_thread = thread

    def stats(self):
        """ Return the current stats object. Just a simple counter based
            report on what the client has been up to. Adds one parameter
            `timestamp` which holds the current epoch time
        """
        stats = self._stats.copy()
        stats['timestamp'] = time.time()
        queue_stats = {}
        for queue_name, concurrency_queue in self._concurrency_queues.items():
            queue_stats[queue_name] = concurrency_queue.stats()
        stats['queues'] = queue_stats
        return stats

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
                  'serializers', 'auto_reconnect', 'sslopt', 'sockopt',
                  'loop_timeout', 'heartbeat_timeout', 'ping_interval',
                  'concurrency_class',
                  'concurrency_max',
                  'concurrency_queue_max',
                  'concurrency_configs',
                  'concurrency_strict_naming'
                  ):

            if k in kwargs:
                setattr(self,k,kwargs[k])

    def concurrency_config_get(self, queue_name):
        """ Returns the normalized config for a particular queue
            if available

            Attributes allowed in the concurrency_configs maybe:

            {
                concurrency_max: integer,
                queue_max: integer,
                loop_timeout: float,

                _class: class to use when creating this queue.
                        When required the _class will be invoked with
                        _class( queue_name, **normalized_config )
            }

        """

        # System defaults
        config = {
            'concurrency_max': self.concurrency_max or 0,
            'queue_max': self.concurrency_queue_max or 0,
            'loop_timeout': self.loop_timeout,
            '_class': self.concurrency_class or ConcurrencyQueue,
        }

        if queue_name == 'unlimited':
            config['concurrency_max'] = 0
            config['queue_max'] = 0

        # Preset defaults if available
        configs = self.concurrency_configs or {}
        default_config = configs.get('default', {})
        config.update(default_config)

        # We don't need to proceed further
        if queue_name == 'default':
            return config

        # Get the configuration to be passed along to the instantiator
        # if we don't have one created, 
        queue_config = configs.get(queue_name,{})
        config.update(queue_config)

        return config

    def concurrency_queue_create(self, queue_name):
        """ Creates a new ConcurrencyQueue instance
        """
        concurrency_config = self.concurrency_config_get(queue_name)
        klass = concurrency_config['_class']
        concurrency_queue = klass(queue_name, **concurrency_config)
        return concurrency_queue


    def concurrency_queue_allowed(self, queue_name):
        """ Returns a true value if the concurrency queue is allowed
        """
        if queue_name in ('default', 'unlimited'):
            return True
        if self.concurrency_configs and queue_name in self.concurrency_configs:
            return True

        # If we want to prevent errors in speling for the queue names, we can force
        # the queue names to be strict with self.concurrency_strict_name = True
        # By default this is ON
        if self.concurrency_strict_naming:
            return False
        return True

    def concurrency_queue_get(self, queue_name):
        """ Returns the queue identified by `queue_name`. If no queue exists by 
            that name (yet) and self.concurrency_strict_naming exists, the
            queue will be instantiated and returned

            If a queue by the name `queue_name` does not already exist, creates
            it with the concurrency_configs value. If concurrency_configs value is a 
            simple int, will use that. If it's a dict, will first search for
            the `queue_name` and a value and use that if present otherwise looks
            for "default" and uses that one instead

            If the `queue_name` is `unlimited`, this will put the invocation or
            subscription into a queue that runs immediately regardless of the
            current default concurrency limit globally set.

            If the `queue_name` has not been defined explicitly by the user
            at instantiation, it will silently create one but use the system
            default queue size
        """

        if not self.concurrency_queue_allowed(queue_name):
            raise ExNotImplemented("{} queue has not been defined!".format(queue_name))

        if queue_name not in self._concurrency_queues:
            new_queue = self.concurrency_queue_create(queue_name)
            self._concurrency_queues[queue_name] = new_queue
        concurrency_queue = self._concurrency_queues[queue_name]

        # Just in case, let's start the queue thread
        if not concurrency_queue.is_alive():
            concurrency_queue.start()

        return concurrency_queue

    def concurrency_queue_run(self, runner, queue_name=None ):
        """ Puts a single runnable into the concurrency queue based upon
            the name of the queue. If no queue_name is provided, defaults
            to 'default'
        """
        if not queue_name:
            queue_name = 'default'
        self.concurrency_queue_get(queue_name).put(runner)

    def handle_challenge(self,data):
        """ Executed when the server requests additional
            authentication
        """
        raise NotImplemented("Received Challenge but authentication not possible. Need to subclass 'handle_challenge'?")

    def handle_connect(self):
        """ When the transport has initially connected
        """
        pass

    def transport_connect(self, **options):
        """ Attempt to hook up the transport
        """
        self.transport = get_transport(
                            self.url,
                            **options)
        self.transport.connect()
        self.handle_connect()

    def handle_join(self,details):

        # Then rebind all the registrations and callbacks
        # if there's a need
        if details.details['authmethod'] != 'anonymous':
            self.heartbeat()
        to_register = self._registered_calls
        self._registered_calls = {}
        for uri, callback, queue_name in to_register.values():
            self.register(uri, callback, queue_name)

        to_subscribe = self._subscriptions
        self._subscriptions = {}
        for uri, callback, queue_name in to_subscribe.values():
            self.subscribe(uri, callback, queue_name)

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
            raise ExWAMPConnectionError("WAMP is currently disconnected!")

        self._stats['calls'] += 1

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

    def receive_message(self, data):
        """ Receives a message data from the transport and normalizes
            it into a WampMessage
        """
        message = WampMessage.load(data)
        return message

    def send_message(self,message):
        """ Send awamp message to the server. We don't wait
            for a response here. Just fire out a message
        """
        if self._state == STATE_DISCONNECTED:
            raise ExWAMPConnectionError("WAMP is currently disconnected!")
        if not self.transport:
            raise ExWAMPConnectionError("WAMP is currently disconnected!")
        logger.debug("SND>: {}".format(message))
        self.transport.send_message(message)

    def send_and_await_response(self,request):
        """ Used by most things. Sends out a request then awaits a response
            keyed by the request_id
        """
        if self._state == STATE_DISCONNECTED:
            raise ExWAMPConnectionError("WAMP is currently disconnected!")
        wait_queue = queue.Queue()
        request_id = request.request_id
        self._requests_pending[request_id] = wait_queue;
        self.send_message(request)
        try:
            res = wait_queue.get(block=True,timeout=self.timeout)
        except queue.Empty as ex:
            raise Exception("Did not receive a response!")
        if isinstance(res, GOODBYE):
            raise ExWAMPConnectionError("WAMP is currently disconnected!")
        return res

    def dispatch_to_awaiting(self,result):
        """ Send data to the appropriate queues
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
        self._stats['errors'] += 1
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
        self._stats['invocations'] += 1
        req_id = message.request_id
        reg_id = message.registration_id
        if reg_id in self._registered_calls:
            handler = self._registered_calls[reg_id][REGISTERED_CALL_CALLBACK]
            queue_name = self._registered_calls[reg_id][REGISTERED_CALL_QUEUE_NAME]
            runner = WampInvokeWrapper(handler,message,self)
            try:
                self.concurrency_queue_run(runner,queue_name)
            except Exception as ex:
                error_uri = self.get_full_uri('error.invoke.failed')
                self.send_message(ERROR(
                    request_code = WAMP_INVOCATION,
                    request_id = req_id,
                    details = {},
                    error = error_uri,
                    args = [str(ex)],
                ))
        else:
            error_uri = self.get_full_uri('error.unknown.uri')
            self.send_message(ERROR(
                request_code = WAMP_INVOCATION,
                request_id = req_id,
                details = {},
                error = error_uri
            ))

    def handle_event(self, event):
        """ Send the event to the subclass or simply reject
        """
        self._stats['events'] += 1
        subscription_id = event.subscription_id
        if subscription_id in self._subscriptions:
            # FIXME: [1] should be a constant
            handler = self._subscriptions[subscription_id][SUBSCRIPTION_CALLBACK]
            queue_name = self._subscriptions[subscription_id][SUBSCRIPTION_QUEUE_NAME]
            runner = WampSubscriptionWrapper(handler,event,self)

            # Since this is a subscription event, we will merely dispose
            # the error right now. 
            try:
                self.concurrency_queue_run(runner, queue_name)
            except Exception as ex:
                logger.warning(
                    "Subscription event receipt failed because {ex}".format(
                      ex = str(ex)
                    )
                )

    def handle_unknown(self, message):
        """ We don't know what to do with this. So we'll send it
            into the queue just in case someone wants to do something
            with it but we'll just blackhole it.
        """
        self.dispatch_to_awaiting(message)

    def subscribe(self,topic,callback=None,options=None,concurrency_queue=None):
        """ Subscribe to a uri for events from a publisher
        """
        # If a concurrency queue is requested, check the queue if required
        if concurrency_queue and not self.concurrency_queue_allowed(concurrency_queue):
            raise ExNotImplemented("{} queue has not been defined!".format(concurrency_queue))

        full_topic = self.get_full_uri(topic)
        result = self.send_and_await_response(SUBSCRIBE(
                                    options=options or {},
                                    topic=full_topic
                                ))
        if result == WAMP_SUBSCRIBED:
            if not callback:
                callback = lambda a: None
            self._subscriptions[result.subscription_id] = [topic,callback,concurrency_queue]
        return result

    def unsubscribe(self, subscription_id):
        """ Unsubscribe an existing subscription
        """
        result = self.send_and_await_response(UNSUBSCRIBE(subscription_id=subscription_id))
        try:
            del self._subscriptions[subscription_id]
        except IndexError:
            logger.warning(
                "Subscription ID '{}' not found in local subscription list. Sent unsubscribe to router anyway.".format(subscription_id)
              )
        return result

    def publish(self,topic,options=None,args=None,kwargs=None):
        """ Publishes a messages to the server
        """
        self._stats['publications'] += 1
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
            return None

    def disconnect(self):
        """ Disconnect from the transport and pause the process
            till we reconnect
        """
        logger.debug("Disconnecting")

        # Close off the transport 
        if self.transport:
            try:
                if self._state == STATE_CONNECTED:
                    self.handle_leave()
                    self.stop_heartbeat()
                    self.send_message(GOODBYE(
                          details={},
                          reason="wamp.error.system_shutdown"
                        ))
                logger.debug("Closing Websocket")
                try:
                    self.transport.close()
                except Exception as ex:
                    logger.debug("Could not close transport because: {}".format(ex))
            except Exception as ex:
                logger.debug("Could not send Goodbye message because {}".format(ex))
                pass # FIXME: Maybe do better handling here
            self.transport = None

        # Cleanup the state variables. By settings this
        # we're going to be telling the main loop to stop
        # trying to read from a transport and await a notice
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
        self._last_ping_time = None
        self._last_pong_time = None
        self.handle_disconnect()


    def shutdown(self):
        """ Request the system to shutdown the main loop and shutdown the system
            This is a one-way trip! Reconnecting requires a new connection
            to be made!
        """
        self._request_shutdown = True

        # Shutdown any responses pending
        if self._concurrency_queues:
            for concurrency_queue in self._concurrency_queues.values():
                concurrency_queue.active = False
            self._concurrency_queues = None

        # Trigger an exception in the reading thread so we can stop the
        # read loop faster
        try:
            res = ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(self.ident),
                                                             ctypes.py_object(ExShutdown))

        # This gets triggered typically when running under pypy as it does
        # not implement the ctypes.pythonapi layer
        # see: https://doc.pypy.org/en/latest/discussion/ctypes-implementation.html
        except AttributeError:
            pass

        for i in range(100):
            if self._state == STATE_DISCONNECTED:
                break
            time.sleep(0.1)

    def start(self, **options):
        """ Initialize the transport, say hello, and start listening for events
        """
        self.connect(**options)
        if not self.is_alive():
            super(WAMPClient,self).start()
        self.hello()
        return self

    def reconnect(self):
        """ Attempt to reconnect to the WAMP server. Thia also assumes that
            the main loop is still running
        """

        # Reset the connection
        self.connect(soft_reset=True)

        # Add to the stats
        self._stats['reconnections'] += 1

        # And hello hello
        self.hello()

        return self

    def unregister(self, registration_id):
        result = self.send_and_await_response(UNREGISTER(registration_id=registration_id))
        if result == WAMP_UNREGISTERED:
            del self._registered_calls[registration_id]
        elif result == WAMP_ERROR:
            if result.args:
                err = result.args
            else:
                err = [result.error]
            raise ExInvocationError(*err)

        return result

    def register(self,uri,callback,details=None,concurrency_queue=None):
        """ Puts a function on the bus.

            - uri: ustring URI to put on the bus
            - callback: method invoked to respond to any calls made to URI
            - details: dict of options
            - concurrency_queue: string. By default a queue for each registration is used
                The maximum sizes of the concurrency queues are set the session attribute
                `self.concurrency_map`

        """
        # If a concurrency queue is requested, check the queue if required
        if concurrency_queue and not self.concurrency_queue_allowed(concurrency_queue):
            raise ExNotImplemented("{} queue has not been defined!".format(concurrency_queue))

        full_uri = self.get_full_uri(uri)
        result = self.send_and_await_response(REGISTER(
                      details=details or {},
                      procedure=full_uri
                  ))
        if result == WAMP_REGISTERED:
            self._registered_calls[result.registration_id] = [ uri, callback, concurrency_queue ]
        elif result == WAMP_ERROR:
            if result.args:
                err = result.args
            else:
                err = [result.error]
            raise ExInvocationError(*err)

        return result

    def run(self):
        """ Waits and receives messages from the server. This
            function somewhat needs to block so is executed in its
            own thread until self._request_shutdown is called.
        """
        data = None

        while not self._request_shutdown:

            # Find out if we have any data pending from the
            # server
            try:
                if self._last_pong_time:
                    since_last_pong = time.time() - self._last_pong_time
                else:
                    since_last_pong = None

                # If we've been asked to stop running the
                # request loop. We'll just sit and wait
                # till we get asked to run again
                if self._state not in [STATE_AUTHENTICATING,STATE_WEBSOCKET_CONNECTED,STATE_CONNECTED]:
                    self._request_loop_notify_restart.acquire()
                    self._request_loop_notify_restart.wait(self.loop_timeout)
                    self._request_loop_notify_restart.release()
                    continue

                # If we don't have a transport defined.
                # we don't go further either
                elif not self.transport:
                    logger.debug("No longer have a transport. Marking disconnected")
                    self._state = STATE_DISCONNECTED
                    continue

                if since_last_pong and since_last_pong > self.heartbeat_timeout:
                    # If the last ping response happened too long
                    # ago, consider it a transport timeout and
                    # handle disconnect.
                        raise ExWAMPConnectionError(
                                  "Maximum transport response delay of %s secs exceeded.",
                                  self.heartbeat_timeout
                              )

                # Okay, we think we're okay so let's try and read some data
                data = self.transport.next()
                if not data: continue

            except ExShutdown:
                self._state = STATE_DISCONNECTED
                return
            except io.BlockingIOError:
                continue
            except (ExWAMPConnectionError) as ex:
                logger.debug("Transport Exception. Requesting disconnect:".format(ex))
                self._state = STATE_DISCONNECTED
                self.stop_heartbeat()
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
                logger.error(
                    "ERROR in main loop: {ex}\n{traceback}".format(
                        ex=ex,
                        traceback=traceback.format_exc(),
                    )
                  )
                continue

            try:
                logger.debug("<RCV: {}".format(data))
                message = self.receive_message(data)
                self._stats['messages'] += 1
                logger.debug("<RCV: {}".format(message.dump()))
                try:
                    code_name = message.code_name.lower()
                    handler_name = "handle_"+code_name
                    handler_function = getattr(self,handler_name)
                    handler_function(message)
                except AttributeError as ex:
                    self.handle_unknown(message)
            except Exception as ex:
                logger.error("ERROR in main loop when receiving: {ex}\n{traceback}".format(
                    ex=ex,
                    traceback=traceback.format_exc(),
                ))

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



