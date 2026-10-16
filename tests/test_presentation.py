from desktranslate.models import SessionState
from desktranslate.presentation import session_presentation


def test_terminal_one_shot_has_no_live_actions_and_keeps_failure_recoverable():
    for result in (True, False):
        view = session_presentation(SessionState.WATCHING, completed=True, has_result=result)
        assert "not capturing" in view.summary
        assert not view.can_pause and not view.can_stop
    failed = session_presentation(SessionState.ERROR, completed=True)
    assert failed.can_pause and failed.can_stop and "Retry" in failed.pause_text


def test_region_selection_and_preparation_can_be_cancelled_without_enabling_pause():
    selecting = session_presentation(None, selecting=True, preparation="needed")
    assert "Escape" in selecting.summary and selecting.can_stop and not selecting.can_pause
    for stage in ("needed", "downloading"):
        preparing = session_presentation(None, preparation=stage)
        assert "not capturing" in preparing.summary and preparing.can_stop
        assert not preparing.can_pause


def test_paused_waiting_and_idle_states_have_distinct_feedback():
    paused = session_presentation(SessionState.PAUSED)
    assert paused.pause_text == "Resume" and "capture stopped" in paused.summary
    waiting = session_presentation(SessionState.WAITING_TARGET)
    assert "Waiting" in waiting.summary and waiting.can_pause
    idle = session_presentation(None)
    retiring = session_presentation(None, retiring=True)
    assert "Ready" in idle.summary and "Stopping" in retiring.summary
    assert not idle.can_pause and not retiring.can_pause
