from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

from desktranslate.errors import ConfigurationError, CredentialError


def validate_endpoint(url: str, local: bool = False) -> str:
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError:
        raise ConfigurationError("Enter a valid API endpoint.") from None
    if (
        parts.scheme not in {"https", "http"}
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
        or "\\" in url
        or any(ord(c) < 33 for c in url)
    ):
        raise ConfigurationError(
            "Use an HTTPS endpoint, or HTTP on localhost, without credentials or query parameters."
        )
    try:
        loopback = ipaddress.ip_address(parts.hostname).is_loopback
    except ValueError:
        loopback = parts.hostname.lower() == "localhost"
    if (parts.scheme == "http" and not loopback) or (local and not loopback):
        raise ConfigurationError(
            "Local providers must use localhost. Remote endpoints require HTTPS."
        )
    if port is not None and not 1 <= port <= 65535:
        raise ConfigurationError("Invalid endpoint port.")
    return url.strip().rstrip("/")


class CredentialStore:
    service = "DeskTranslate2"

    def _backend(self) -> object:
        import keyring

        backend = keyring.get_keyring()
        # Explicitly disallow plaintext/fail/chained third-party backends.
        if not type(backend).__module__.startswith(
            (
                "keyring.backends.Windows",
                "keyring.backends.macOS",
                "keyring.backends.SecretService",
                "keyring.backends.kwallet",
            )
        ):
            raise CredentialError()
        return backend

    def get(self, account: str) -> str:
        try:
            backend = self._backend()
            return backend.get_password(self.service, account) or ""  # type: ignore[attr-defined,no-any-return]
        except Exception:
            raise CredentialError() from None

    def set(self, account: str, key: str) -> None:
        try:
            backend = self._backend()
            backend.set_password(self.service, account, key)  # type: ignore[attr-defined]
        except Exception:
            raise CredentialError() from None

    def delete(self, account: str) -> None:
        try:
            backend = self._backend()
            if backend.get_password(self.service, account):  # type: ignore[attr-defined]
                backend.delete_password(self.service, account)  # type: ignore[attr-defined]
        except Exception:
            raise CredentialError() from None
