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

from audio import (
    AUTHORIZED,
    DENIED,
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


def test_a_delivery_from_the_live_task_is_passed_along():
    pipeline, transcripts, errors = build_pipeline()

    pipeline._handle_result(1, FakeResult(), None)
    pipeline._handle_result(1, None, FakeError())

    assert transcripts == ["the words that were said"]
    assert len(errors) == 1


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
