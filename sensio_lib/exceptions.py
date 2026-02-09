"""Custom exceptions for sensio_lib."""


class SensioException(Exception):
    """Base exception for sensio_lib."""


class SensioAuthenticationError(SensioException):
    """Raised when authentication with the Sensio API fails."""


class SensioConnectionError(SensioException):
    """Raised when connection to the Sensio controller fails."""


class SensioCommandError(SensioException):
    """Raised when a command to the Sensio controller fails."""
