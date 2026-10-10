"""User-safe failures. Raw provider responses and exception strings never reach logs."""


class DeskTranslateError(Exception):
    message = "Something went wrong. Try again or copy diagnostics."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)


class CaptureError(DeskTranslateError):
    message = "This region cannot be captured. Try windowed mode or select another region."


class DisplayChangedError(CaptureError):
    message = "Your display layout changed. Select the region again."


class TargetUnavailableError(CaptureError):
    message = "Waiting for the chosen application. Restore it or select its window again."


class OCRInitializationError(DeskTranslateError):
    message = "Recognition is not ready. Open Recognition and prepare the models."


class OCRLanguageMissingError(OCRInitializationError):
    message = "Recognition for this language is not installed. Open Recognition to install it."


class OCRInferenceError(DeskTranslateError):
    message = "Recognition failed. Try a larger region or another recognition engine."


class TranslationError(DeskTranslateError):
    message = "The provider returned an invalid translation. Try again or choose another model."


class ProviderAuthenticationError(TranslationError):
    message = "Your API key was rejected. Replace it in Providers and test the connection."


class ProviderRateLimitError(TranslationError):
    message = "The provider is busy or your quota is exhausted. Wait, then resume."

    def __init__(self, retry_after: float = 10.0) -> None:
        self.retry_after = min(120.0, max(1.0, retry_after))
        super().__init__()


class ProviderUnavailableError(TranslationError):
    message = "Cannot reach the provider. Check your connection and test it in Providers."


class ProviderTimeoutError(TranslationError):
    message = "The provider took too long. Try a faster model or resume to retry."


class ModelNotFoundError(TranslationError):
    message = "This model is unavailable. Refresh the model list and select another."


class LocalServerUnavailableError(ProviderUnavailableError):
    message = "Local AI is not running. Start Ollama or LM Studio, load a model, then test again."


class CredentialError(DeskTranslateError):
    message = "Secure credential storage is unavailable. Your key has not been saved."


class ConfigurationError(DeskTranslateError):
    message = "Some settings were invalid. Defaults have been restored."


class Cancelled(DeskTranslateError):
    message = "Operation cancelled."
