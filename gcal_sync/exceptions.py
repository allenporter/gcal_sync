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


class CalendarParseException(ApiException):
    """Raised when parsing a calendar event fails.

    The 'message' attribute contains a human-readable message about the
    error that occurred. The 'detailed_error' attribute can provide additional
    information about the error, such as a stack trace or detailed parsing
    information, useful for debugging purposes.
    """

    def __init__(self, message: str, *, detailed_error: str | None = None) -> None:
        """Initialize the CalendarParseError with a message."""
        super().__init__(message)
        self.message = message
        self.detailed_error = detailed_error
