"""Authentication library, implemented by users of the library."""

from abc import ABC, abstractmethod

from google.auth.credentials import Credentials


class AbstractAuth(ABC):  # pylint: disable=too-few-public-methods
    """Library for providing authentication credentials."""

    @abstractmethod
    async def async_get_creds(self) -> Credentials:
        """Return an OAuth credential for the calendar API."""
