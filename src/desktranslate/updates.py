import httpx
from packaging.version import InvalidVersion, Version

from desktranslate import __version__
from desktranslate.errors import ProviderUnavailableError


def check_release() -> tuple[str, str] | None:
    try:
        with httpx.Client(timeout=6, follow_redirects=False) as client:
            response = client.get(
                "https://api.github.com/repos/DeskTranslate/DeskTranslate/releases/latest",
                headers={"Accept": "application/vnd.github+json"},
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            release = response.json()
        tag = release["tag_name"]
        url = release["html_url"]
        if not url.startswith("https://github.com/DeskTranslate/DeskTranslate/releases/"):
            return None
        if Version(tag.lstrip("v")) > Version(__version__):
            return tag, url
    except (httpx.HTTPError, ValueError, KeyError, TypeError, InvalidVersion):
        raise ProviderUnavailableError(
            "Cannot check updates. Visit the GitHub releases page later."
        ) from None
    return None
