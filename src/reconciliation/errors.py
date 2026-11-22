class ReconciliationError(Exception):
    """A predictable failure the CLI can report without a traceback."""


class ConfigurationError(ReconciliationError):
    """An invalid or unsupported comparison configuration."""


class InputFileError(ReconciliationError):
    """A missing, unreadable or structurally invalid input."""


class OutputError(ReconciliationError):
    """A report could not be written without overwriting existing data."""


class InvalidValue(ValueError):
    """An individual value cannot be normalized with the selected rule."""
