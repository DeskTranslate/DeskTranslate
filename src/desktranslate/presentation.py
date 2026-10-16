"""User-facing session semantics, independent of widgets and worker ownership."""

from dataclasses import dataclass
from typing import Literal

from desktranslate.models import SessionState


@dataclass(frozen=True)
class SessionPresentation:
    summary: str
    pause_text: str
    can_pause: bool
    can_stop: bool


def session_presentation(
    state: SessionState | None,
    *,
    selecting: bool = False,
    retiring: bool = False,
    completed: bool = False,
    has_result: bool = False,
    preparation: Literal["needed", "downloading"] | None = None,
    restart_required: bool = False,
) -> SessionPresentation:
    if restart_required:
        return SessionPresentation("Restart required · capture stopped", "Pause", False, False)
    if selecting:
        return SessionPresentation(
            "Selecting a region · Enter confirms, Escape cancels", "Pause", False, True
        )
    if preparation:
        return SessionPresentation(
            "Preparing recognition · not capturing"
            if preparation == "downloading"
            else "Language pack needed · install to continue · not capturing",
            "Pause",
            False,
            True,
        )
    if state is None:
        return SessionPresentation(
            "Stopping · no new capture" if retiring else "Ready · not capturing",
            "Pause",
            False,
            False,
        )
    if completed and state != SessionState.ERROR:
        return SessionPresentation(
            "Translation complete · not capturing"
            if has_result
            else "No text found · not capturing",
            "Pause",
            False,
            False,
        )
    if state == SessionState.PAUSED:
        return SessionPresentation("Paused · capture stopped", "Resume", True, True)
    if state == SessionState.ERROR:
        return SessionPresentation(
            "Translation paused · see Translate for details", "Retry translation", True, True
        )
    summaries = {
        SessionState.STARTING: "Starting translation…",
        SessionState.WATCHING: "Live · watching selected content",
        SessionState.WAITING_TARGET: "Waiting for the chosen application",
        SessionState.RECOGNIZING: "Reading text locally…",
        SessionState.TRANSLATING: "Translating recognized text…",
        SessionState.STOPPING: "Stopping · no new capture",
        SessionState.IDLE: "Ready · not capturing",
        SessionState.SELECTING: "Selecting a region · Enter confirms, Escape cancels",
    }
    active = state not in {SessionState.IDLE, SessionState.STOPPING, SessionState.SELECTING}
    return SessionPresentation(summaries[state], "Pause", active, active)
