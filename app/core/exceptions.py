class FinderError(Exception):
    """Base exception for the application."""


class ConfigurationError(FinderError):
    """Raised when application configuration is invalid."""


class DatabaseError(FinderError):
    """Raised when a database operation fails."""


class DatasetError(FinderError):
    """Raised when a DOL dataset cannot be processed."""


class DatasetValidationError(DatasetError):
    """Raised when a dataset fails validation."""


class DownloadError(DatasetError):
    """Raised when a dataset cannot be downloaded."""