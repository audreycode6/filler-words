"""Streaming speech from the microphone into whatever wants to count it.

`SpeechPipeline` holds the 4 Apple objects that have to be alive together --
the audio engine, the tap on its input, the recognition request and the
recognition task -- starts and stops them in the right order, and hands each
transcript to a callback. It knows nothing about segments or tracked words: it
produces the text that `matcher.py` turns into counts.

Both of this stack's silent failures are refused here rather than inherited:

 - A denied microphone returns zeros from an engine that reported success, so
   authorization is read before anything starts.
 - Recognition runs on Apple's servers unless asked to stay on the machine, so
   a machine that cannot raises OnDeviceUnavailable.

The app drives SpeechPipeline from the menu bar. Running the module instead
checks it on its own:

    python src/audio.py [seconds]

docs/design-decisions.md carries the reasoning behind this design.
"""

import logging
import time

import AVFoundation
import Foundation
import Speech

logger = logging.getLogger(__name__)

# How long 1 slice of the run loop runs before the caller gets a turn back.
RUN_LOOP_SLICE_SECONDS = 0.1

# The audio engine's input node carries a single bus, numbered 0. The same bus
# is read for its format, tapped, and untapped.
INPUT_BUS = 0

# How many frames of audio to ask for per tap callback. A request rather than a
# guarantee: Spike 1 asked for this figure and was handed buffers of 4800.
TAP_BUFFER_FRAMES = 1024

# What the app can be in as far as listening goes. AUTHORIZED is the only one
# that starts anything; the other 3 are what the interface reports instead.
AUTHORIZED = "authorized"
DENIED = "denied"
RESTRICTED = "restricted"
UNDETERMINED = "undetermined"

_MIC_STATES = {
    0: UNDETERMINED,  # AVAuthorizationStatusNotDetermined
    1: RESTRICTED,  # AVAuthorizationStatusRestricted
    2: DENIED,  # AVAuthorizationStatusDenied
    3: AUTHORIZED,  # AVAuthorizationStatusAuthorized
}
_SPEECH_STATES = {
    0: UNDETERMINED,  # SFSpeechRecognizerAuthorizationStatusNotDetermined
    1: DENIED,  # SFSpeechRecognizerAuthorizationStatusDenied
    2: RESTRICTED,  # SFSpeechRecognizerAuthorizationStatusRestricted
    3: AUTHORIZED,  # SFSpeechRecognizerAuthorizationStatusAuthorized
}

# The 4 states ranked worst to best. `_state_for` walks this in order and
# reports the first state either status maps to, so the one that blocks wins
# and AUTHORIZED is reached only when both statuses are authorized.
_SEVERITY_ORDER = (DENIED, RESTRICTED, UNDETERMINED, AUTHORIZED)


class OnDeviceUnavailable(Exception):
    """Raised when this machine cannot recognize speech without the network.

    Separate from the authorization states because nobody can grant it. The
    server path exists and would run, which is exactly why this is an error:
    it stops after about a minute with no error raised, so a run that quietly
    used it would look like a working app that counts most of a session as
    silence.
    """


def _describe_error(error):
    """Write an NSError out as its domain, its code and its description.

    Anything that is not an NSError is written out whole.
    """
    if not hasattr(error, "domain"):
        return str(error)

    return (
        f"domain={error.domain()} code={error.code()}"
        f" :: {error.localizedDescription()}"
    )


def _states_for(mic_status, speech_status):
    """Map each authorization status to a state, keeping the 2 apart.

    A status neither framework has documented is treated as RESTRICTED, being
    the closest true thing the app can say: listening is unavailable, and
    asking again will not change it.
    """
    return (
        _MIC_STATES.get(mic_status, RESTRICTED),
        _SPEECH_STATES.get(speech_status, RESTRICTED),
    )


def _state_for(mic_status, speech_status):
    """Reduce the 2 authorization statuses to 1 reportable state."""
    states = _states_for(mic_status, speech_status)

    for state in _SEVERITY_ORDER:
        if state in states:
            return state


def _statuses():
    """Read both authorization statuses now, without prompting for either."""
    return (
        AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
            AVFoundation.AVMediaTypeAudio
        ),
        Speech.SFSpeechRecognizer.authorizationStatus(),
    )


def authorization_state():
    """The one state the app acts on."""
    return _state_for(*_statuses())


def authorization_detail():
    """The reported state, then the microphone's own and speech recognition's.

    Read without prompting, as `authorization_state` does.
    """
    statuses = _statuses()
    mic_state, speech_state = _states_for(*statuses)
    return _state_for(*statuses), mic_state, speech_state


def request_authorization(when_decided):
    """Prompt for whichever permission has not been asked for yet.

    `when_decided` is called with the state the 2 statuses came to once the
    person has answered. A callback rather than a return value because the
    prompts are answered on the person's own time, and the run loop has to keep
    turning while they are on screen.
    """

    def speech_decided(_status):
        # The status this is handed is for speech alone. Read both back
        # instead, so 1 place decides what the pair of them means.
        when_decided(authorization_state())

    def microphone_decided(_granted):
        Speech.SFSpeechRecognizer.requestAuthorization_(speech_decided)

    AVFoundation.AVCaptureDevice.requestAccessForMediaType_completionHandler_(
        AVFoundation.AVMediaTypeAudio, microphone_decided
    )


class SpeechPipeline:
    """The microphone, the recognizer, and the transcripts running between them.

    Built once and started and stopped as many times as there are sessions. The
    request and the task are made fresh on each start, since a task that has
    been cancelled cannot be reused.

    `on_transcript` is called with the whole transcript so far, every time the
    recognizer revises it. `on_error` is called with an NSError when
    recognition reports one. Both are called on whichever thread the recognizer
    delivers to; a caller that touches an interface is responsible for getting
    itself back to the main thread.

    `pump_run_loop` is for callers with no event loop of their own. An
    application running `NSApplication.run()` already runs the run loop these
    callbacks arrive on and leaves this false; a script has to run it itself
    or receive nothing at all, with no error to say why.
    """

    def __init__(self, on_transcript, on_error=None, pump_run_loop=False):
        self._on_transcript = on_transcript
        self._on_error = on_error
        self._pump_run_loop = pump_run_loop

        self._recognizer = None
        self._engine = None
        self._request = None
        self._task = None

        # start() numbers each recognition task; only the live number's
        # deliveries are kept.
        self._task_count = 0
        self._live_task_number = None

    @property
    def is_running(self):
        return self._engine is not None

    def start(self):
        """Begin listening, returning the authorization state it found.

        Nothing is built and no engine is started unless that state is
        AUTHORIZED, so a caller can report the reason without having to undo
        anything. Raises OnDeviceUnavailable when this machine would need the
        network to recognize speech.
        """
        if self.is_running:
            return AUTHORIZED

        state = authorization_state()
        if state != AUTHORIZED:
            return state

        if self._recognizer is None:
            self._recognizer = Speech.SFSpeechRecognizer.alloc().init()

        self._request = self._build_request()

        self._task_count += 1
        self._live_task_number = self._task_count
        task_number = self._task_count

        self._task = self._recognizer.recognitionTaskWithRequest_resultHandler_(
            self._request,
            lambda result, error: self._handle_result(task_number, result, error),
        )
        self._engine = self._build_engine()

        started, error = self._engine.startAndReturnError_(None)
        if not started:
            self.stop()
            raise RuntimeError(f"the audio engine did not start: {error}")

        return AUTHORIZED

    def stop(self):
        """Stop listening and release everything start() built.

        Unwound in the order the engine expects: the audio stops, then the tap
        comes off the bus feeding it, then the request is told no more audio is
        coming, and only then is the task cancelled. Stopping something that
        was never started, or stopping twice, does nothing. The live task number
        is retired first, so a stopped pipeline delivers nothing.
        """
        self._live_task_number = None

        if self._engine is not None:
            self._engine.stop()
            self._engine.inputNode().removeTapOnBus_(INPUT_BUS)
            self._engine = None

        if self._request is not None:
            self._request.endAudio()
            self._request = None

        if self._task is not None:
            self._task.cancel()
            self._task = None

    def pump(self, seconds):
        """Turn the run loop for a while, so callbacks have somewhere to arrive.

        Recognition results are delivered by the Cocoa run loop. Sleeping
        instead of turning it produces a run with no transcripts and no error,
        which reads like a microphone that hears nothing.

        Returns early once the pipeline has been stopped. Does nothing at all
        unless the pipeline was built with pump_run_loop.
        """
        if not self._pump_run_loop:
            return

        run_loop = Foundation.NSRunLoop.currentRunLoop()
        until = time.monotonic() + seconds
        while time.monotonic() < until and self.is_running:
            slice_end = Foundation.NSDate.dateWithTimeIntervalSinceNow_(
                RUN_LOOP_SLICE_SECONDS
            )
            run_loop.runUntilDate_(slice_end)

    def _build_request(self):
        """A recognition request that streams, and never leaves the machine."""
        # Checked before it is set
        if not self._recognizer.supportsOnDeviceRecognition():
            raise OnDeviceUnavailable(
                "this machine cannot recognize speech on device for its locale, "
                "and the server path is refused"
            )

        request = Speech.SFSpeechAudioBufferRecognitionRequest.alloc().init()
        request.setShouldReportPartialResults_(True)
        request.setRequiresOnDeviceRecognition_(True)

        return request

    def _build_engine(self):
        """An audio engine with its input tapped into the recognition request."""
        engine = AVFoundation.AVAudioEngine.alloc().init()
        input_node = engine.inputNode()
        input_format = input_node.inputFormatForBus_(INPUT_BUS)

        request = self._request

        def append_audio(buffer, when):
            request.appendAudioPCMBuffer_(buffer)

        input_node.installTapOnBus_bufferSize_format_block_(
            INPUT_BUS, TAP_BUFFER_FRAMES, input_format, append_audio
        )

        return engine

    def _handle_result(self, task_number, result, error):
        """Take 1 delivery from the recognizer and pass the text along.

        `task_number` is the number the delivering task was started under.
        A delivery from any number other than the live one is dropped.
        """
        if task_number != self._live_task_number:
            return

        if error is not None:
            logger.error("recognition failed: %s", _describe_error(error))
            if self._on_error is not None:
                self._on_error(error)
            return

        if result is None:
            return

        self._on_transcript(result.bestTranscription().formattedString())


# --- running the pipeline on its own -----------------------------------------


DEFAULT_CHECK_SECONDS = 180

# A gap this long between transcripts, while speech continues, is the failure
# this check is looking for: recognition stopping without saying so. Held above
# the quiet spell before a rollover, measured at 8.5s in a 181-second run, and
# well under the ~61s at which the server path dies in silence.
CONTINUITY_GAP_SECONDS = 20


def _run_check(seconds):
    """Stream for a while and report whether it held up.

    Prints the permission state by name before anything starts, every
    transcript as it arrives, and a verdict at the end. The verdict is the
    point: a gap in the middle of a long run is invisible while it scrolls
    past, and only shows up as a number.
    """
    state = authorization_state()
    print(f"Authorization: {state}")

    if state == UNDETERMINED:
        print("Asking. Answer the prompts...")
        decided = []
        request_authorization(decided.append)

        # Nothing has been built yet, so pump a plain run loop rather than the
        # pipeline's, and give up rather than hang if the prompts go unanswered.
        run_loop = Foundation.NSRunLoop.currentRunLoop()
        deadline = time.monotonic() + 60
        while not decided and time.monotonic() < deadline:
            run_loop.runUntilDate_(
                Foundation.NSDate.dateWithTimeIntervalSinceNow_(RUN_LOOP_SLICE_SECONDS)
            )

        state = decided[0] if decided else authorization_state()
        print(f"Authorization: {state}")

    if state != AUTHORIZED:
        print(
            "Refusing to start. Nothing was recorded and no engine was run --\n"
            "a run without permission returns silence, due to no audio input.\n"
            "Grant access in System Settings > Privacy & Security, under both\n"
            "Microphone and Speech Recognition."
        )
        return 1

    started_at = time.monotonic()
    arrivals = []

    def show(transcript):
        arrivals.append(time.monotonic())
        print(f"[+{time.monotonic() - started_at:7.2f}s] {transcript}")

    def complain(error):
        print(f"[+{time.monotonic() - started_at:7.2f}s] ERROR {error}")

    pipeline = SpeechPipeline(show, on_error=complain, pump_run_loop=True)

    try:
        pipeline.start()
    except OnDeviceUnavailable as unavailable:
        print(f"Refusing to start: {unavailable}")
        return 2

    print(f"Listening for {seconds}s -- talk now, and keep talking.")
    try:
        pipeline.pump(seconds)
    except KeyboardInterrupt:
        # Report on the partial run rather than unwinding past the summary,
        # which is the only output the check produces.
        print("\nInterrupted -- reporting on the partial run.")
    finally:
        pipeline.stop()

    elapsed = time.monotonic() - started_at
    gaps = [
        later - earlier for earlier, later in zip([started_at] + arrivals, arrivals)
    ]
    longest_gap = max(gaps, default=elapsed)

    print(
        f"\nSummary: ran {elapsed:.1f}s | transcripts={len(arrivals)} | "
        f"longest gap={longest_gap:.1f}s"
    )
    if not arrivals:
        print("FAIL: no transcripts ever arrived.")
        return 1
    if longest_gap > CONTINUITY_GAP_SECONDS:
        print(
            f"FAIL: recognition went quiet for {longest_gap:.1f}s, "
            f"over the {CONTINUITY_GAP_SECONDS}s this is checking for."
        )
        return 1

    print("OK: transcripts arrived continuously for the whole run.")
    return 0


if __name__ == "__main__":
    import sys

    requested = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CHECK_SECONDS
    sys.exit(_run_check(requested))
