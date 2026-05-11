"""
Custom exceptions for the post-processing module.

This module defines a hierarchy of exceptions for handling post-processing
errors in a structured way, enabling graceful degradation and clear error
messages for users.
"""

from __future__ import annotations

from typing import Optional


class PostProcessingError(Exception):
    """
    Base exception for all post-processing errors.

    All post-processing-related exceptions should inherit from this class
    to enable catch-all handling while allowing specific error types.

    Attributes:
        message: Human-readable error description
        details: Optional additional context or debugging information
    """

    def __init__(self, message: str, details: Optional[str] = None) -> None:
        """
        Initialize PostProcessingError.

        Args:
            message: Primary error message
            details: Additional context (e.g., file paths, field names)
        """
        self.message = message
        self.details = details
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format the complete error message."""
        if self.details:
            return f"{self.message}\n  Details: {self.details}"
        return self.message


class MissingFieldError(PostProcessingError):
    """
    Required field data not found in the OpenFOAM case.

    Raised when a visualization or hemodynamics calculation requires a field
    that doesn't exist in the case (e.g., wallShearStressMean for TAWSS).

    Example:
        >>> raise MissingFieldError("wallShearStressMean", "TAWSS calculation")
        MissingFieldError: Field 'wallShearStressMean' not found
          Required for: TAWSS calculation
          Hint: Ensure fieldAverage is enabled in controlDict
    """

    def __init__(self, field_name: str, required_for: Optional[str] = None, hint: Optional[str] = None) -> None:
        """
        Initialize MissingFieldError.

        Args:
            field_name: Name of the missing field
            required_for: What operation requires this field
            hint: Suggestion for how to fix the issue
        """
        self.field_name = field_name
        self.required_for = required_for
        self.hint = hint

        message = f"Field '{field_name}' not found"
        details_parts = []
        if required_for:
            details_parts.append(f"Required for: {required_for}")
        if hint:
            details_parts.append(f"Hint: {hint}")

        super().__init__(message, "\n  ".join(details_parts) if details_parts else None)


class ParaViewError(PostProcessingError):
    """
    ParaView pipeline or rendering error.

    Raised when ParaView encounters an error during visualization,
    such as failed reader initialization or rendering issues.

    Example:
        >>> raise ParaViewError("Camera PCA computation failed", "No points in dataset")
    """

    def __init__(self, operation: str, reason: Optional[str] = None) -> None:
        """
        Initialize ParaViewError.

        Args:
            operation: The ParaView operation that failed
            reason: Why the operation failed
        """
        self.operation = operation
        self.reason = reason

        message = f"ParaView error: {operation}"
        super().__init__(message, reason)


class ConfigurationError(PostProcessingError):
    """
    Invalid post-processing configuration.

    Raised when the configuration contains invalid values, missing required
    fields, or incompatible settings.

    Example:
        >>> raise ConfigurationError(
        ...     "Invalid time_steps value",
        ...     value="invalid",
        ...     valid_options="None, 'last', 'peak', or list of floats"
        ... )
    """

    def __init__(self, message: str, value: Optional[str] = None, valid_options: Optional[str] = None) -> None:
        """
        Initialize ConfigurationError.

        Args:
            message: Error description
            value: The invalid value that was provided
            valid_options: Description of valid options
        """
        self.value = value
        self.valid_options = valid_options

        details_parts = []
        if value is not None:
            details_parts.append(f"Got: {value}")
        if valid_options:
            details_parts.append(f"Valid options: {valid_options}")

        super().__init__(message, "\n  ".join(details_parts) if details_parts else None)


class CaseNotFoundError(PostProcessingError):
    """
    OpenFOAM case directory not found or invalid.

    Raised when the specified case path doesn't exist or doesn't contain
    the expected OpenFOAM case structure.

    Example:
        >>> raise CaseNotFoundError("/path/to/case", "No .foam file found")
    """

    def __init__(self, case_path: str, reason: Optional[str] = None) -> None:
        """
        Initialize CaseNotFoundError.

        Args:
            case_path: Path that was searched
            reason: Why the case is invalid
        """
        self.case_path = case_path
        message = f"OpenFOAM case not found: {case_path}"
        super().__init__(message, reason)


class DependencyError(PostProcessingError):
    """
    Required dependency not available.

    Raised when a required external tool (e.g., ParaView, ffmpeg) is not
    installed or not accessible.

    Example:
        >>> raise DependencyError("ffmpeg", "Animation generation")
    """

    def __init__(self, dependency: str, required_for: str) -> None:
        """
        Initialize DependencyError.

        Args:
            dependency: Name of the missing dependency
            required_for: What feature requires this dependency
        """
        self.dependency = dependency
        self.required_for = required_for

        message = f"Dependency '{dependency}' not found"
        super().__init__(message, f"Required for: {required_for}")


class HemodynamicsError(PostProcessingError):
    """
    Error during hemodynamics calculation.

    Raised when computing hemodynamic metrics (TAWSS, OSI, RRT) fails,
    typically due to missing data or invalid field values.

    Example:
        >>> raise HemodynamicsError(
        ...     "OSI calculation failed",
        ...     metric="OSI",
        ...     reason="Division by zero (TAWSS = 0)"
        ... )
    """

    def __init__(self, message: str, metric: Optional[str] = None, reason: Optional[str] = None) -> None:
        """
        Initialize HemodynamicsError.

        Args:
            message: Error description
            metric: Which metric failed (TAWSS, OSI, RRT)
            reason: Technical reason for failure
        """
        self.metric = metric
        self.reason = reason

        details_parts = []
        if metric:
            details_parts.append(f"Metric: {metric}")
        if reason:
            details_parts.append(f"Reason: {reason}")

        super().__init__(message, "\n  ".join(details_parts) if details_parts else None)
