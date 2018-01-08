
class SwampyException(Exception):
    pass

class ExWelcomeTimeout(SwampyException):
    pass

class ExAbort(SwampyException):
    pass

class ExInvocationError(SwampyException):
    pass
