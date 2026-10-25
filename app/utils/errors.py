"""Application-level exceptions with user-friendly messages."""

from __future__ import annotations


class FinTwinError(Exception):
    """Base class for expected, user-presentable errors."""

    user_message = "Something went wrong. Please try again."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.user_message)
        self.message = message or self.user_message


class ValidationError(FinTwinError):
    """Raised when user input fails validation."""

    user_message = "Some of the information entered is not valid."


class AuthenticationError(FinTwinError):
    """Raised when credentials are wrong or the session is invalid."""

    user_message = "Invalid email or password."


class DatabaseUnavailableError(FinTwinError):
    """Raised when MongoDB cannot be reached."""

    user_message = (
        "Unable to connect to MongoDB. Please check whether MongoDB is running, "
        "or set MONGO_URI=mongomock://localhost in .env to use demo mode."
    )


class UploadError(FinTwinError):
    """Raised when an uploaded file is rejected."""

    user_message = "The uploaded file could not be processed."


class InsufficientDataError(FinTwinError):
    """Raised when an analysis needs more data than the user has."""

    user_message = "There is not enough transaction history for this analysis yet."
