"""Explicit, bounded release discovery. No executable download or silent installation."""

from __future__ import annotations

import json
import re
import time
from threading import Event
from typing import Any
from urllib.parse import urlsplit

import httpx
from packaging.version import InvalidVersion, Version

from desktranslate import __version__
from desktranslate.errors import Cancelled, ProviderUnavailableError

RELEASES = "https://api.github.com/repos/DeskTranslate/DeskTranslate/releases"


def choose_release(
    releases: Any, channel: str, current: str = __version__
) -> tuple[str, str] | None:
    if channel not in {"stable", "beta"}:
        raise ValueError("Choose Stable or Beta updates")
    if not isinstance(releases, list) or len(releases) > 100:
        raise ValueError("Invalid release metadata")
    candidates: list[tuple[Version, str, str]] = []
    for release in releases:
        if not isinstance(release, dict) or release.get("draft"):
            continue
        tag, url = release.get("tag_name"), release.get("html_url")
        if not isinstance(tag, str) or not re.fullmatch(r"v?2\.\d+\.\d+(?:(?:b|rc)\d+)?", tag):
            continue
        version = Version(tag.removeprefix("v"))
        if channel == "stable" and (release.get("prerelease") or version.is_prerelease):
            continue
        if version.is_prerelease != bool(release.get("prerelease")):
            continue
        expected = "/DeskTranslate/DeskTranslate/releases/tag/" + tag
        if not isinstance(url, str):
            continue
        parts = urlsplit(url)
        if (
            parts.scheme != "https"
            or parts.netloc != "github.com"
            or parts.path != expected
            or parts.query
            or parts.fragment
        ):
            continue
        assets = release.get("assets", [])
        if not isinstance(assets, list) or not any(
            isinstance(a, dict) and a.get("name") == f"DeskTranslate-{version}-Setup-x64.exe"
            for a in assets
        ):
            continue
        if version > Version(current):
            candidates.append((version, tag, url))
    if not candidates:
        return None
    _, tag, url = max(candidates)
    return tag, url


def check_release(
    channel: str = "stable",
    cancel: Event | None = None,
    transport: httpx.BaseTransport | None = None,
) -> tuple[str, str] | None:
    cancel = cancel or Event()
    deadline = time.monotonic() + 12
    try:
        with httpx.Client(
            timeout=httpx.Timeout(6, connect=4), follow_redirects=False, transport=transport
        ) as client:
            releases: list[dict[str, Any]] = []
            for page in range(1, 4):
                if cancel.is_set():
                    raise Cancelled()
                with client.stream(
                    "GET",
                    RELEASES,
                    params={"per_page": 30, "page": page},
                    headers={"Accept": "application/vnd.github+json"},
                ) as response:
                    response.raise_for_status()
                    content = bytearray()
                    for chunk in response.iter_bytes():
                        if cancel.is_set():
                            raise Cancelled()
                        if time.monotonic() > deadline or len(content) + len(chunk) > 1_000_000:
                            raise ValueError("Release metadata limit")
                        content.extend(chunk)
                    payload = json.loads(content)
                if not isinstance(payload, list) or len(payload) > 30:
                    raise ValueError("Invalid release catalog")
                releases.extend(payload)
                if len(payload) < 30:
                    break
            return choose_release(releases, channel)
    except (httpx.HTTPError, ValueError, KeyError, TypeError, InvalidVersion):
        raise ProviderUnavailableError(
            "Cannot check updates. Visit the GitHub releases page later."
        ) from None
