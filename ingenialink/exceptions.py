class ILError(Exception):
    """ IngeniaLink generic error. """
    pass


class ILCreationError(ILError):
    """ IngeniaLink creation error. """
    pass


class ILValueError(ILError):
    """ IngeniaLink value error. """
    pass


class ILTimeoutError(ILError):
    """ IngeniaLink timeout error. """
    pass


class ILAlreadyInitializedError(ILError):
    """ InteniaLink already initialized error. """
    pass


class ILMemoryError(ILError):
    """ IngeniaLink memory error. """
    pass


class ILDisconnectionError(ILError):
    """ IngeniaLink disconnection error. """
    pass


class ILAccessError(ILError):
    """ IngeniaLink access error. """
    pass


class ILStateError(ILError):
    """ IngeniaLink state error. """
    pass


class ILIOError(ILError):
    """ IngeniaLink I/O error. """
    pass
