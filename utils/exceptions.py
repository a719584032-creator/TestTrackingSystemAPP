"""Common exception classes used throughout the application."""
from __future__ import annotations


class ClientError(Exception):
    """Base error for recoverable client issues."""


class AuthenticationError(ClientError):
    """Raised when the remote service rejects user credentials."""


class ValidationError(ClientError):
    """Raised when the UI layer detects invalid user input."""


class NetworkError(ClientError):
    """Raised when an HTTP request cannot be completed."""


class UpdateError(ClientError):
    """Raised when the OTA update workflow fails."""
