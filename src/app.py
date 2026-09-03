"""The entry point, and the wiring between the 4 pieces that make the app.

Each of the other modules stands alone: `audio.py` produces transcripts,
`matcher.py` turns a finished segment into counts, `session.py` holds the
totals, and `menubar.py` draws them. This module builds one of each and decides
who calls whom.

docs/design-decisions.md carries the reasoning behind this design.
"""

import logging
import os
import sys

import audio
from config import TRACKED_WORDS
from matcher import SegmentTracker, count_tracked
from menubar import MenuBarApp, on_main
from session import Session

# Diagnostics go to the terminal that launched the app.
LOG_FORMAT = "%(asctime)s %(name)s %(levelname)s %(message)s"
LOG_TIME_FORMAT = "%H:%M:%S"

# Set in the environment to log every transcript through the app.
DEBUG_VARIABLE = "VERBAL_HABITS_DEBUG"

logger = logging.getLogger(__name__)


class VerbalHabits:
    """One session's worth of objects, and the callbacks running between them.

    The tracked list is an argument, so the app can be built around a list
    other than the shipped one. The pipeline and the menu are taken as callables
    that build them, so a test supplies stand-ins and runs without a microphone
    or a window server.
    """

    def __init__(
        self,
        tracked_words=TRACKED_WORDS,
        build_pipeline=audio.SpeechPipeline,
        build_menu=MenuBarApp,
    ):
        self._tracked_words = tracked_words
        self._session = Session(self._tracked_words)
        self._tracker = SegmentTracker()
        self._folds = 0
        self._commits = 0

        self._pipeline = build_pipeline(
            self._took_transcript,
            on_error=self._took_error,
            on_stalled=self._took_stall,
        )
        self._menu = build_menu(
            self._session,
            on_start=self._start_listening,
            on_stop=self._stop_listening,
            read_authorization=audio.authorization_detail,
        )

    def run(self):
        """Turn the run loop until the app is quit."""
        self._menu.run()

    # --- what the menu calls ---

    def _start_listening(self):
        """Begin listening, returning the authorization state it found.

        An undetermined state prompts and returns, and the answer arrives at
        `_authorization_decided`.
        """
        state = audio.authorization_state()
        if state == audio.UNDETERMINED:
            audio.request_authorization(self._authorization_decided)
            return state

        if state != audio.AUTHORIZED:
            return state

        # A fresh tracker, holding no previous transcript from the last session.
        self._tracker = SegmentTracker()
        return self._pipeline.start()

    def _stop_listening(self):
        """Stop listening, folding in the segment still open."""
        self._pipeline.stop()

        segment = self._tracker.flush()
        if segment is not None:
            self._session.record(*count_tracked(segment, self._tracked_words))

    def _authorization_decided(self, _state):
        """Take the answer to the permission prompts back to the menu's Start.

        The state is settled by the time this runs, so starting again takes
        whichever path that state calls for.
        """
        on_main(self._menu.start)

    # --- what the pipeline calls ---

    def _took_transcript(self, transcript):
        """Take one transcript from the recognizer, on whatever thread it came in on."""
        on_main(lambda: self._fold(transcript))

    def _took_error(self, _error):
        """End the session on a recognition error, which audio.py has written out."""
        on_main(self._menu.recognition_failed)

    def _took_stall(self, device_name):
        """End the session when the microphone stops sending audio."""
        on_main(lambda: self._menu.input_stopped(device_name))

    def _fold(self, transcript):
        """Count whatever segment this transcript finished, then have the menu
        reread the session.

        Runs on the main thread, which is the thread the totals are read from.
        """
        self._folds += 1
        logger.debug("fold %d, %d characters", self._folds, len(transcript))

        segment = self._tracker.update(transcript)
        if segment is not None:
            self._commits += 1
            logger.debug("commit %d, %d characters", self._commits, len(segment))
            self._session.record(*count_tracked(segment, self._tracked_words))

        self._menu.refresh()


def main():
    logging.basicConfig(
        level=logging.DEBUG if os.environ.get(DEBUG_VARIABLE) else logging.INFO,
        format=LOG_FORMAT,
        datefmt=LOG_TIME_FORMAT,
        stream=sys.stderr,
    )
    VerbalHabits().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
