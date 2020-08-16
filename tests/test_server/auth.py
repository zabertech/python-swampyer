from __future__ import print_function

import os
import base64

# Packages to allow us to bind to the crossbar server as a component
from twisted.internet.defer import inlineCallbacks
from twisted.internet import reactor, task
from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.exception import ApplicationError

from autobahn.wamp.types import SubscribeOptions, RegisterOptions

PASS_FILE = 'test-password.txt'
AUTH_URI = 'swampyer.test.authenticator.ticket'

# This provides password support
class Authenticator(ApplicationSession):

    rand_pass = None

    @inlineCallbacks
    def onJoin(self, details):

        # Create or load the temporary password for test cases
        if os.path.exists(PASS_FILE):
            print("Reading new password")
            with open(PASS_FILE,'r') as f:
                self.rand_pass = f.read()

        if not self.rand_pass:
            print("Writing new password")
            self.rand_pass = base64.b64encode(os.urandom(32)).decode('utf8')
            with open(PASS_FILE,'w') as f:
                f.write(self.rand_pass)
        print("New password is '{}'".format(self.rand_pass))
        
        # Hook up the authentication service
        try:
            print("REGISTERING: {}!".format(AUTH_URI))
            yield self.register(
                    self.authenticate_ticket,
                    AUTH_URI,
                    options=RegisterOptions(details_arg='details')
                  )

            yield self.register(
                      self.create_otp,
                      '',
                  )
        except Exception as ex:
            print(ex)


    def authenticate_ticket(self, realm, authid, request, details):
        try:
            if self.rand_pass == request['ticket']:
                return {
                    'role': 'trust',
                    'realm': realm,
                    'extra': {
                      'test_data': 'hi'
                    }
                }
            raise ApplicationError(AUTH_URI, "Could not authenticate session. Password did not match.")
        except Exception as ex:
            raise ApplicationError('Invalid Login')

