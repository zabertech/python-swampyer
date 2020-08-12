import re

# Packages to allow us to bind to the crossbar server as a component
from twisted.internet.defer import inlineCallbacks
from twisted.internet import reactor, task
from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.exception import ApplicationError

from autobahn.wamp.types import SubscribeOptions, RegisterOptions


class EchoSession(ApplicationSession):

    @inlineCallbacks
    def onJoin(self, details):
        try:
            print("REGISTERING: swampyer.test.swampyer.echo!")
            yield self.register(
                    self.echo,
                    'swampyer.test.swampyer.echo',
                    options=RegisterOptions(details_arg='details')
                  )
        except Exception as ex:
            print(ex)


    def echo(self, data, details, *args, **kwargs):
        return data
