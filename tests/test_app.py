"""The wiring between the pieces, which is all `app.py` holds.

Each piece is covered by its own tests. What is tested here is the order the
callbacks run in: that the last thing said before a stop is still counted, that
a new session counts nothing from the one before it, and that the error a
cancelled task reports stays out of the menu.

These tests open no microphone and build no AppKit object. The pipeline and the
menu are taken by the app as callables that build them, so each test hands in a
stand-in. The tracked list here is this file's own, so changing what the app
tracks changes no test.
"""

import pytest

import app
import audio
from app import VerbalHabits

WORDS = ("well", "bro")


class FakeMenu:
    """Stands in for MenuBarApp, recording what the app asked it to show.

    Start and stop follow the real app's order:
    the session begins only once the app reports an authorized state, and
    the app is told to stop while the session is still active.
    """

    def __init__(self, session, on_start, on_stop, read_authorization):
        self.session = session
        self.read_authorization = read_authorization
        self._on_start = on_start
        self._on_stop = on_stop
        self.refreshes = 0
        self.errors = []

    def start(self):
        state = self._on_start()
        if state == audio.AUTHORIZED:
            self.session.start()
            self.refresh()
        return state

    def stop(self):
        self._on_stop()
        self.session.stop()
        self.refresh()

    def refresh(self):
        self.refreshes += 1

    def report_error(self, error):
        self.errors.append(str(error))


class FakePipeline:
    """Stands in for SpeechPipeline, taking the callbacks and counting stops.

    Stopping reports an error, as cancelling a real recognition task does.
    """

    def __init__(self, on_transcript, on_error=None, state=audio.AUTHORIZED):
        self.on_transcript = on_transcript
        self.on_error = on_error
        self.state = state
        self.starts = 0
        self.stops = 0

    def start(self):
        self.starts += 1
        return self.state

    def stop(self):
        self.stops += 1
        if self.on_error is not None:
            self.on_error("the recognition task was cancelled")


def build():
    """An app holding stand-ins for the pipeline and the menu.

    A test sets the authorization state by patching `audio.authorization_state`.
    """

    def build_pipeline(on_transcript, on_error=None):
        return FakePipeline(on_transcript, on_error)

    return VerbalHabits(WORDS, build_pipeline=build_pipeline, build_menu=FakeMenu)


@pytest.fixture(autouse=True)
def run_on_main_inline(monkeypatch):
    """Run what the app dispatches straight away, since a test turns no run loop."""
    monkeypatch.setattr(app, "on_main", lambda work: work())


@pytest.fixture
def authorized(monkeypatch):
    monkeypatch.setattr(audio, "authorization_state", lambda: audio.AUTHORIZED)


# --- counting while a session runs -------------------------------------------


def test_a_committed_segment_folds_into_the_totals(authorized):
    verbal = build()
    verbal._menu.start()

    for transcript in ("well", "well bro", "well bro again", "ok"):
        verbal._pipeline.on_transcript(transcript)

    assert verbal._session.counts == {"well": 1, "bro": 1}
    assert verbal._session.total_word_count == 3


def test_the_menu_is_refreshed_for_every_transcript(authorized):
    verbal = build()
    verbal._menu.start()
    before = verbal._menu.refreshes

    verbal._pipeline.on_transcript("well")
    verbal._pipeline.on_transcript("well bro")

    assert verbal._menu.refreshes == before + 2


# --- stopping ----------------------------------------------------------------


def test_the_segment_still_open_folds_into_the_totals_on_a_stop(authorized):
    verbal = build()
    verbal._menu.start()
    verbal._pipeline.on_transcript("well and bro")

    verbal._menu.stop()

    assert verbal._session.counts == {"well": 1, "bro": 1}
    assert verbal._pipeline.stops == 1


def test_the_error_a_cancelled_task_reports_stays_out_of_the_menu(authorized):
    verbal = build()
    verbal._menu.start()

    verbal._menu.stop()

    assert verbal._menu.errors == []


def test_an_error_while_listening_reaches_the_menu(authorized):
    verbal = build()
    verbal._menu.start()

    verbal._pipeline.on_error("recognition stopped")

    assert verbal._menu.errors == ["recognition stopped"]


# --- starting again ----------------------------------------------------------


def test_a_second_session_counts_nothing_from_the_first(authorized):
    verbal = build()
    verbal._menu.start()
    verbal._pipeline.on_transcript("well and bro and well and bro and well again")
    verbal._menu.stop()

    # A short transcript after a long one is what a rollover looks like, so a
    # tracker carried over would commit the first session's speech here.
    verbal._menu.start()
    verbal._pipeline.on_transcript("ok")

    assert verbal._session.counts == {"well": 0, "bro": 0}
    assert verbal._session.total_word_count == 0


# --- authorization -----------------------------------------------------------


def test_an_undetermined_state_asks_for_authorization(monkeypatch):
    asked = []
    monkeypatch.setattr(audio, "authorization_state", lambda: audio.UNDETERMINED)
    monkeypatch.setattr(
        audio, "request_authorization", lambda when_decided: asked.append(when_decided)
    )
    verbal = build()

    state = verbal._start_listening()

    assert state == audio.UNDETERMINED
    assert len(asked) == 1
    assert verbal._pipeline.starts == 0


def test_a_refusal_starts_nothing(monkeypatch):
    monkeypatch.setattr(audio, "authorization_state", lambda: audio.DENIED)
    verbal = build()

    state = verbal._start_listening()

    assert state == audio.DENIED
    assert verbal._pipeline.starts == 0
    assert verbal._session.is_active is False


def test_an_answered_prompt_starts_the_session(monkeypatch):
    monkeypatch.setattr(audio, "authorization_state", lambda: audio.AUTHORIZED)
    verbal = build()

    verbal._authorization_decided(audio.AUTHORIZED)

    assert verbal._pipeline.starts == 1
