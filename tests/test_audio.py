"""The 2 authorization statuses (microphone & speech recognizer)
become 1 state the interface can report.

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

from audio import AUTHORIZED, DENIED, RESTRICTED, UNDETERMINED, _state_for

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
