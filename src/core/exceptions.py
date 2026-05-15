"""Custom exceptions for TeleChat application."""

from __future__ import annotations


class TeleChatError(Exception):
    """Base exception for all TeleChat errors."""

    pass


# Configuration Errors
class ConfigError(TeleChatError):
    """Base class for configuration-related errors."""

    pass


class MissingConfigError(ConfigError):
    """Raised when required configuration is missing."""

    pass


class InvalidConfigError(ConfigError):
    """Raised when configuration value is invalid."""

    pass


# Permission Errors
class PermissionError(TeleChatError):
    """Raised when user lacks required permissions."""

    pass


class PermissionDeniedError(PermissionError):
    """Raised when access is denied due to lack of permissions."""

    pass


class AdminRequiredError(PermissionError):
    """Raised when admin privileges are required."""

    pass


class GroupAdminRequiredError(PermissionError):
    """Raised when group admin privileges are required."""

    pass


# Database Errors
class DatabaseError(TeleChatError):
    """Base class for database-related errors."""

    pass


class EntityNotFoundError(DatabaseError):
    """Raised when requested entity is not found in database."""

    pass


class DuplicateEntityError(DatabaseError):
    """Raised when trying to create a duplicate entity."""

    pass


class TransactionError(DatabaseError):
    """Raised when database transaction fails."""

    pass


# Provider Errors
class ProviderError(TeleChatError):
    """Base class for AI provider-related errors."""

    pass


class NoProvidersAvailableError(ProviderError):
    """Raised when no providers are available for the requested model."""

    pass


class NoActiveProviderError(ProviderError):
    """Raised when no active provider is found."""

    pass


class NoActiveAPIKeyError(ProviderError):
    """Raised when no active API key is found for a provider."""

    pass


class ProviderNotFoundError(ProviderError):
    """Raised when provider is not found."""

    pass


class ProviderResponseError(ProviderError):
    """Raised when provider returns an error response."""

    pass


class ProviderTimeoutError(ProviderError):
    """Raised when provider request times out."""

    pass


# AI Client Errors
class AIClientError(TeleChatError):
    """Base class for AI client-related errors."""

    pass


class StreamingError(AIClientError):
    """Raised when streaming response fails."""

    pass


class ModelNotFoundError(AIClientError):
    """Raised when requested model is not found."""

    pass


class UnsupportedMediaError(AIClientError):
    """Raised when an AI provider does not support the input media type."""

    pass


# Input Validation Errors
class ValidationError(TeleChatError):
    """Base class for input validation errors."""

    pass


class InvalidTimeFormatError(ValidationError):
    """Raised when time format is invalid."""

    pass


class InvalidCommandArgumentsError(ValidationError):
    """Raised when command arguments are invalid."""

    pass


# Message Errors
class MessageError(TeleChatError):
    """Base class for message-related errors."""

    pass


class UnsupportedMediaTypeError(MessageError):
    """Raised when media type is not supported."""

    pass


class MessageTooLongError(MessageError):
    """Raised when message exceeds maximum length."""

    pass
