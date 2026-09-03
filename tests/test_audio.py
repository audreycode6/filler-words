"""The 2 authorization statuses (microphone & speech recognizer) become 1 state
the interface can report, and a delivery is matched to the task it came from.

macOS reports permission as a small integer. Reconciling them is what `_state_for` does.

These tests never open a microphone. They call `_state_for` directly, below the
framework calls that read the 2 statuses, so every combination can be put in by
hand. That includes the 2 restricted states, which appear only on a Mac held
under a configuration profile or parental controls and cannot be produced by
clicking through System Settings on a personal machine.

Each status is written out below as the literal integer macOS returns, under
this file's own name for it. Note: The 2 statuses put denied and restricted in
opposite positions. The values were read back from the installed
frameworks when this was written.
"""

import audio
from audio import (
    AUTHORIZED,
    DENIED,
    RESTARTS_BEFORE_GIVING_UP,
    RESTART_WINDOW_SECONDS,
    STALL_SECONDS,
    RESTRICTED,
    UNDETERMINED,
    SpeechPipeline,
    _describe_error,
    _state_for,
    _states_for,
)

# AVAuthorizationStatus -- microphone
MIC_UNDETERMINED = 0
MIC_RESTRICTED = 1
MIC_DENIED = 2
MIC_AUTHORIZED = 3

# SFSpeechRecognizerAuthorizationStatus -- speech recognition
SPEECH_UNDETERMINED = 0
SPEECH_DENIED = 1
SPEECH_RESTRICTED = 2
SPEECH_AUTHORIZED = 3


# --- a refusal from either side ----------------------------------------------


def test_a_denied_microphone_reports_denied():
    assert _state_for(MIC_DENIED, SPEECH_AUTHORIZED) == DENIED


def test_denied_speech_recognition_reports_denied():
    assert _state_for(MIC_AUTHORIZED, SPEECH_DENIED) == DENIED


def test_a_restricted_microphone_reports_restricted():
    assert _state_for(MIC_RESTRICTED, SPEECH_AUTHORIZED) == RESTRICTED


def test_restricted_speech_recognition_reports_restricted():
    assert _state_for(MIC_AUTHORIZED, SPEECH_RESTRICTED) == RESTRICTED


# --- both sides agreeing -----------------------------------------------------


def test_both_authorized_reports_authorized():
    # The only state that starts the engine.
    assert _state_for(MIC_AUTHORIZED, SPEECH_AUTHORIZED) == AUTHORIZED


def test_a_status_nobody_has_been_asked_for_reports_undetermined():
    assert _state_for(MIC_UNDETERMINED, SPEECH_AUTHORIZED) == UNDETERMINED


# --- ranking the two against each other --------------------------------------


def test_a_refusal_outranks_a_permission_not_yet_asked_for():
    # Prompting for the microphone would put a dialog on screen and leave the
    # app no better off, because the other side is already a no.
    assert _state_for(MIC_UNDETERMINED, SPEECH_DENIED) == DENIED


def test_an_unrecognized_status_never_reports_authorized():
    # A later macOS adding a fourth value must not be read as permission. What
    # it reports instead is the module's to choose; that it does not start the
    # engine is not.
    assert _state_for(MIC_AUTHORIZED, 99) != AUTHORIZED
    assert _state_for(99, SPEECH_AUTHORIZED) != AUTHORIZED


# --- naming which permission was refused -------------------------------------


def test_the_2_states_are_reported_separately():
    # The interface has to say which permission was refused: the 2 are granted
    # on separate System Settings panes.
    assert _states_for(MIC_DENIED, SPEECH_AUTHORIZED) == (DENIED, AUTHORIZED)
    assert _states_for(MIC_AUTHORIZED, SPEECH_DENIED) == (AUTHORIZED, DENIED)


def test_an_undocumented_status_is_restricted_on_its_own_side():
    assert _states_for(99, SPEECH_AUTHORIZED) == (RESTRICTED, AUTHORIZED)
    assert _states_for(MIC_AUTHORIZED, 99) == (AUTHORIZED, RESTRICTED)


# --- writing an error out ----------------------------------------------------


# Invented: _describe_error reads 3 methods and joins what they return,
# whatever that is.
FAKE_DOMAIN = "FakeErrorDomain"
FAKE_CODE = 99
FAKE_DESCRIPTION = "the recognizer gave up"


class FakeError:
    """An NSError as far as this module reads one."""

    def domain(self):
        return FAKE_DOMAIN

    def code(self):
        return FAKE_CODE

    def localizedDescription(self):
        return FAKE_DESCRIPTION


def test_an_error_is_written_out_by_domain_code_and_description():
    # What a terminal is left holding after a session fails. The 3 are read
    # separately because the whole NSError prints as one unreadable line.
    written = _describe_error(FakeError())

    assert FAKE_DOMAIN in written
    assert str(FAKE_CODE) in written
    assert FAKE_DESCRIPTION in written


def test_something_that_is_not_an_error_is_written_out_whole():
    assert _describe_error("recognition stopped") == "recognition stopped"


# --- which task a delivery came from -----------------------------------------

# Each start takes a number that its result handler carries. These tests set
# `_live_task_number` directly, standing in for a start, which opens a microphone.


def build_pipeline():
    """A pipeline with 1 live task, numbered 1. Opens nothing."""
    transcripts = []
    errors = []

    pipeline = SpeechPipeline(transcripts.append, on_error=errors.append)
    pipeline._live_task_number = 1

    return pipeline, transcripts, errors


class FakeResult:
    def bestTranscription(self):
        return self

    def formattedString(self):
        return "the words that were said"

    def isFinal(self):
        return False


def test_a_delivery_from_the_live_task_is_passed_along():
    pipeline, transcripts, errors = build_pipeline()

    pipeline._handle_result(1, FakeResult(), None)

    assert transcripts == ["the words that were said"]
    assert errors == []


def test_a_delivery_from_a_retired_task_is_dropped():
    # What a cancelled task reports as it winds down. Read as live it would
    # mark the session that started after it with a failure of its own.
    pipeline, transcripts, errors = build_pipeline()

    pipeline._handle_result(0, FakeResult(), None)
    pipeline._handle_result(0, None, FakeError())

    assert transcripts == []
    assert errors == []


def test_a_stopped_pipeline_delivers_nothing():
    pipeline, transcripts, errors = build_pipeline()

    pipeline.stop()
    pipeline._handle_result(1, FakeResult(), None)
    pipeline._handle_result(1, None, FakeError())

    assert transcripts == []
    assert errors == []


# --- a microphone that stops sending audio -----------------------------------

# The stall check reads the buffer count the tap keeps. These tests move both
# the count and the clock by hand, standing in for a start, which opens a
# microphone and puts the check on a timer.


class FakeClock:
    """A clock that moves only when a test moves it."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def move(self, seconds):
        self.now += seconds


def build_watched_pipeline(device_name="Audrey's Earphones"):
    """A pipeline watching a buffer count, as start() leaves it. Opens nothing."""
    stalls = []
    clock = FakeClock()

    pipeline = SpeechPipeline(
        lambda _transcript: None, on_stalled=stalls.append, clock=clock
    )
    pipeline._device_name = device_name
    pipeline._buffers_moved_at = clock()

    return pipeline, stalls, clock


def test_a_count_that_keeps_moving_reports_nothing():
    pipeline, stalls, clock = build_watched_pipeline()

    for _ in range(STALL_SECONDS + 2):
        pipeline._buffers += 10
        clock.move(1)
        pipeline._check_for_a_stall()

    assert stalls == []


def test_a_count_that_has_only_just_stopped_reports_nothing():
    # Buffers arrive in bursts, so a count is expected to sit still briefly.
    pipeline, stalls, clock = build_watched_pipeline()

    clock.move(STALL_SECONDS - 1)
    pipeline._check_for_a_stall()

    assert stalls == []


def test_a_count_that_stands_still_reports_the_device_it_was_reading():
    pipeline, stalls, clock = build_watched_pipeline()

    clock.move(STALL_SECONDS)
    pipeline._check_for_a_stall()

    assert stalls == ["Audrey's Earphones"]


def test_a_stall_is_reported_once():
    # Whoever takes the report ends the session. A second report would end the
    # session that replaced it.
    pipeline, stalls, clock = build_watched_pipeline()

    clock.move(STALL_SECONDS)
    pipeline._check_for_a_stall()
    clock.move(STALL_SECONDS)
    pipeline._check_for_a_stall()

    assert stalls == ["Audrey's Earphones"]


def test_a_machine_with_no_named_device_still_reports():
    pipeline, stalls, clock = build_watched_pipeline(device_name="")

    clock.move(STALL_SECONDS)
    pipeline._check_for_a_stall()

    assert stalls == [""]


# --- a recognition task that ends itself -------------------------------------

# Silence ends a task, and the pipeline replaces it where it stands. These
# tests stand in for everything a restart touches: an engine it leaves alone, a
# recognizer that hands out tasks, and a clock the test moves. They open no
# microphone and recognize nothing.


class FinalResult(FakeResult):
    def isFinal(self):
        return True


class FakeTask:
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class FakeRecognizer:
    def __init__(self):
        self.tasks = []

    def supportsOnDeviceRecognition(self):
        return True

    def recognitionTaskWithRequest_resultHandler_(self, request, handler):
        task = FakeTask()
        self.tasks.append(task)
        return task


def build_restartable_pipeline(monkeypatch):
    """A pipeline running task 1 on a stand-in engine, as start() leaves it.

    Work handed to the main thread runs where it was called from, so a restart
    is finished by the time the call that asked for it returns.
    """
    transcripts = []
    errors = []
    clock = FakeClock()

    pipeline = SpeechPipeline(
        transcripts.append, on_error=errors.append, clock=clock
    )
    pipeline._recognizer = FakeRecognizer()
    pipeline._engine = object()
    pipeline._task_count = 1
    pipeline._live_task_number = 1
    pipeline._restart_window_at = clock()

    monkeypatch.setattr(audio, "_on_main", lambda work: work())

    return pipeline, transcripts, errors, clock


def test_an_error_restarts_rather_than_reporting(monkeypatch):
    # The failure that ended a session after 44 seconds of quiet.
    pipeline, transcripts, errors = build_pipeline()
    monkeypatch.setattr(audio, "_on_main", lambda work: work())
    restarts = []
    pipeline._restart = lambda: restarts.append(True)

    pipeline._handle_result(1, None, FakeError())

    assert restarts == [True]
    assert errors == []


def test_a_final_result_restarts(monkeypatch):
    # A task that ends without an error, which is how the session goes deaf.
    pipeline, transcripts, errors = build_pipeline()
    monkeypatch.setattr(audio, "_on_main", lambda work: work())
    restarts = []
    pipeline._restart = lambda: restarts.append(True)

    pipeline._handle_result(1, FinalResult(), None)

    assert transcripts == ["the words that were said"]
    assert restarts == [True]


def test_a_restart_retires_the_task_it_replaced(monkeypatch):
    pipeline, transcripts, errors, clock = build_restartable_pipeline(monkeypatch)

    pipeline._restart()

    assert pipeline._live_task_number == 2
    assert pipeline._recognizer.tasks[-1] is pipeline._task

    # What the task that ended reports as it winds down.
    pipeline._handle_result(1, FakeResult(), None)
    pipeline._handle_result(1, None, FakeError())

    assert transcripts == []
    assert errors == []


def test_a_stopped_pipeline_restarts_nothing():
    pipeline, transcripts, errors = build_pipeline()

    pipeline._restart()

    assert pipeline._task_count == 0
    assert errors == []


def test_restarts_spaced_out_by_silence_never_report(monkeypatch):
    # A quiet room ends a task about once every 45 seconds, for as long as it
    # stays quiet.
    pipeline, transcripts, errors, clock = build_restartable_pipeline(monkeypatch)

    for _ in range(RESTARTS_BEFORE_GIVING_UP * 3):
        clock.move(RESTART_WINDOW_SECONDS)
        pipeline._restart()

    assert errors == []
    assert len(pipeline._recognizer.tasks) == RESTARTS_BEFORE_GIVING_UP * 3


def test_restarts_faster_than_the_window_report_once(monkeypatch):
    pipeline, transcripts, errors, clock = build_restartable_pipeline(monkeypatch)

    for _ in range(RESTARTS_BEFORE_GIVING_UP + 1):
        clock.move(1)
        pipeline._restart()

    assert len(errors) == 1
    assert len(pipeline._recognizer.tasks) == RESTARTS_BEFORE_GIVING_UP
    assert pipeline._live_task_number is None
