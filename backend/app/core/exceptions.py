"""Domain exceptions. Services raise these; app.main maps them to HTTP responses."""


class AppError(Exception):
    status_code = 400
    code = "app_error"

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class AuthError(AppError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class UnsupportedSourceError(AppError):
    status_code = 422
    code = "unsupported_source"


class MediaProcessingError(AppError):
    status_code = 422
    code = "media_processing_failed"


class ExternalServiceError(AppError):
    status_code = 502
    code = "external_service_error"


class ConfigurationError(AppError):
    status_code = 503
    code = "service_not_configured"
