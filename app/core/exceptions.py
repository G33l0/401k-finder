class FinderError(Exception):
    """Base exception for the application."""


class ConfigurationError(FinderError):
    """Raised when application configuration is invalid."""


class DatabaseError(FinderError):
    """Raised when a database operation fails."""


class DatasetError(FinderError):
    """Raised when a DOL dataset cannot be processed."""


class DatasetValidationError(DatasetError):
    """Raised when a dataset does not match its published layout."""


class DownloadError(DatasetError):
    """Raised when a dataset cannot be downloaded."""


class ArchiveError(DatasetError):
    """Raised when a downloaded archive cannot be extracted."""


class CSVReadError(DatasetError):
    """Raised when a dataset CSV file cannot be read."""


class ImportCancelled(FinderError):
    """Raised when the user cancels a running import."""


class SearchError(FinderError):
    """Raised when a search query cannot be executed."""
