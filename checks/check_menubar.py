"""Drive the real menu bar interface from recorded transcripts, with no microphone.

    python checks/check_menubar.py [authorized|denied|restricted]
                                   [microphone|speech|both]

Add "error" to report a recognition failure partway through the replay.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import AppKit
import Foundation

from matcher import SegmentTracker, count_tracked
from menubar import AUTHORIZED, MenuBarApp
from session import Session

CHECK_INTERVAL_SECONDS = 0.4

CHECK_WORDS = ("like", "the", "it", "words", "again", "end")

# How many segments commit before the error check reports one.
CHECK_ERROR_AFTER_SEGMENTS = 2

# 4 segments, each arriving as the whole transcript so far, the way the
# recognizer delivers them. A short opening collapses the one before it, which
# commits that segment.
CHECK_TRANSCRIPTS = (
    "I like",
    "I like the way",
    "I like the way it works",
    "I like the way it works and I like the words",
    "So",
    "So it counts",
    "So it counts the words again",
    "So it counts the words again and again until the end",
    "Then",
    "Then the words",
    "Then the words settle and it is like",
    "Then the words settle and it is like the end again",
    "One",
    "One more time",
    "One more time it says the words",
    "One more time it says the words like the end",
)


def run(forced_state, refused_side, report_error=False):
    """Replay the transcripts into a live status item and menu.

    Transcripts arrive on a timer in the common run loop modes, so both the
    status item and an open menu keep counting while the menu is on screen.
    """
    session = Session(CHECK_WORDS)
    tracker = SegmentTracker()
    replay = iter(CHECK_TRANSCRIPTS)
    reported = False

    mic_state = forced_state if refused_side in ("microphone", "both") else AUTHORIZED
    speech_state = forced_state if refused_side in ("speech", "both") else AUTHORIZED

    def started():
        """Start over the way the app does, on a tracker that has seen nothing."""
        nonlocal tracker, replay, reported
        tracker = SegmentTracker()
        replay = iter(CHECK_TRANSCRIPTS)
        reported = False
        return forced_state

    app = MenuBarApp(
        session,
        on_start=started,
        on_stop=lambda: None,
        read_authorization=lambda: (forced_state, mic_state, speech_state),
    )

    def feed(_timer):
        nonlocal reported
        if not session.is_active:
            return
        if (
            report_error
            and not reported
            and session.segments_counted == CHECK_ERROR_AFTER_SEGMENTS
        ):
            app.recognition_failed()
            reported = True
        try:
            transcript = next(replay)
        except StopIteration:
            segment = tracker.flush()
            if segment is not None:
                session.record(*count_tracked(segment, CHECK_WORDS))
            app.refresh()
            return

        segment = tracker.update(transcript)
        if segment is not None:
            session.record(*count_tracked(segment, CHECK_WORDS))
        app.refresh()

    timer = AppKit.NSTimer.timerWithTimeInterval_repeats_block_(
        CHECK_INTERVAL_SECONDS, True, feed
    )
    Foundation.NSRunLoop.currentRunLoop().addTimer_forMode_(
        timer, Foundation.NSRunLoopCommonModes
    )

    print(f"Reporting authorization as {forced_state}. Open the menu bar item.")
    if report_error:
        print(f"Reporting an error after {CHECK_ERROR_AFTER_SEGMENTS} segments.")
    app.run()
    return 0


if __name__ == "__main__":
    arguments = [argument for argument in sys.argv[1:] if argument != "error"]
    requested = arguments[0] if arguments else AUTHORIZED
    side = arguments[1] if len(arguments) > 1 else "both"
    sys.exit(run(requested, side, report_error="error" in sys.argv[1:]))
