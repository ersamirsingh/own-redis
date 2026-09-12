"""Core exceptions for PyRedis."""


class PyRedisException(Exception):
    """Base exception for all PyRedis errors."""
    pass


class ProtocolError(PyRedisException):
    """Raised when RESP protocol parsing fails."""
    pass


class WrongTypeError(PyRedisException):
    """WRONGTYPE Operation against a key holding the wrong kind of value."""
    def __init__(self, message: str = "WRONGTYPE Operation against a key holding the wrong kind of value"):
        super().__init__(message)


class CommandError(PyRedisException):
    """Generic command syntax or execution error."""
    pass


class AuthError(PyRedisException):
    """Authentication or authorization failure."""
    pass


class OutOfMemoryError(PyRedisException):
    """OOM command not allowed when used memory > maxmemory."""
    def __init__(self, message: str = "OOM command not allowed when used memory > 'maxmemory'"):
        super().__init__(message)
