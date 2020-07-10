
class SwampyException(Exception):
    pass

class ExWelcomeTimeout(SwampyException):
    pass

class ExAbort(SwampyException):
    pass

class ExInvocationError(SwampyException):
    pass

class ExMessageCorrupt(SwampyException):
    pass

class ExWAMPConnectionError(SwampyException):
    pass

# Support for deprecated WAMPConnectionError class
WAMPConnectionError = ExWAMPConnectionError
