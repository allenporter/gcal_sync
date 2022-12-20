"""Library for exceptions using the Google Calendar API."""


class GoogleCalendarException(Exception):
    """Base class for all client exceptions."""


class ApiException(GoogleCalendarException):
    """Raised during problems talking to the API."""


class AuthException(ApiException):
    """Raised due to auth problems talking to API."""


class InvalidSyncTokenException(ApiException):
    """Raised when the sync token is invalid."""


class ApiForbiddenException(ApiException):
    """Raised due to permission errors talking to API."""
