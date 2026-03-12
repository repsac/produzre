"""Custom exception types for configuration parsing and validation."""


class ConfigError(Exception):
    """Raised when the YAML configuration is invalid."""
