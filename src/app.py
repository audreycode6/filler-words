"""The entry point, and the wiring between the 4 pieces that make the app.

Each of the other modules stands alone: `audio.py` produces transcripts,
`matcher.py` turns a finished segment into counts, `session.py` holds the
totals, and `menubar.py` draws them. This module builds one of each and decides
who calls whom.

docs/design-decisions.md carries the reasoning behind this design.
"""

import sys

import audio
from config import TRACKED_WORDS
from matcher import SegmentTracker, count_tracked
from menubar import MenuBarApp, on_main
from session import Session


class VerbalHabits:
    """One session's worth of objects, and the callbacks running between them.

    The tracked list is an argument so that the app can be built around a list
    other than the shipped one. The pipeline and the menu are taken as callables
    that build them, so a test supplies stand-ins and needs neither a microphone
    nor a window server.
    """

    def __init__(
        self,
        tracked_words=TRACKED_WORDS,
        build_pipeline=audio.SpeechPipeline,
        build_menu=MenuBarApp,
    ):
        self._tracked_words = tuple(tracked_words)
        self._session = Session(self._tracked_words)
        self._tracker = SegmentTracker()
        self._listening = False

        self._pipeline = build_pipeline(
            self._took_transcript, on_error=self._took_error
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

        # A fresh tracker, so the first transcript of this session is compared
        # against nothing.
        self._tracker = SegmentTracker()
        self._listening = True
        try:
            return self._pipeline.start()
        except Exception:
            self._listening = False
            raise

    def _stop_listening(self):
        """Stop listening, folding in the segment still open."""
        self._listening = False
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

    def _took_error(self, error):
        """Report an error from the recognizer to the menu while a session listens."""
        if self._listening:
            on_main(lambda: self._menu.report_error(error))

    def _fold(self, transcript):
        """Count whatever segment this transcript finished, then have the menu
        reread the session.

        Runs on the main thread, so the totals are written on the thread they
        are read from.
        """
        segment = self._tracker.update(transcript)
        if segment is not None:
            self._session.record(*count_tracked(segment, self._tracked_words))

        self._menu.refresh()


def main():
    VerbalHabits().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
