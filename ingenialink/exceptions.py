class IngeniaLinkError(Exception):
    """ IngeniaLink generic error. """
    pass


class IngeniaLinkCreationError(IngeniaLinkError):
    """ IngeniaLink creation error. """
    pass


class IngeniaLinkValueError(IngeniaLinkError):
    """ IngeniaLink value error. """
    pass


class IngeniaLinkTimeoutError(IngeniaLinkError):
    """ IngeniaLink timeout error. """
    pass


class IngeniaLinkMemoryError(IngeniaLinkError):
    """ IngeniaLink memory error. """
    pass


class IngeniaLinkDisconnectionError(IngeniaLinkError):
    """ IngeniaLink disconnection error. """
    pass


class IngeniaLinkAccessError(IngeniaLinkError):
    """ IngeniaLink access error. """
    pass


class IngeniaLinkStateError(IngeniaLinkError):
    """ IngeniaLink state error. """
    pass


class IngeniaLinkIOError(IngeniaLinkError):
    """ IngeniaLink I/O error. """
    pass
