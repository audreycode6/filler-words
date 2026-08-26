"""The session holds the totals the interface reads, and nothing else.

These tests never open a microphone and never wait on a real clock. The session
takes a callable for the time, so a test moves time forward by hand. Each test
builds the tracked-word list it needs rather than importing the shipped list, so
that changing what the app tracks changes no test here.
"""

from fixtures import transcripts
from matcher import SegmentTracker, count_tracked
from session import Session


class FakeClock:
    """A clock a test moves by hand, standing in for time.monotonic."""

    def __init__(self):
        self.seconds = 0.0

    def __call__(self):
        return self.seconds

    def advance(self, seconds):
        self.seconds += seconds


# --- before a session starts -------------------------------------------------


def test_a_fresh_session_is_inactive_and_reports_zeros():
    session = Session(["like", "well"])

    assert session.is_active is False
    assert session.counts == {"like": 0, "well": 0}
    assert session.total_word_count == 0
    assert session.total_tracked_count == 0
    assert session.segments_counted == 0
    assert session.elapsed_seconds == 0.0


def test_the_rate_is_zero_before_any_time_has_elapsed():
    # The interface asks for the rate on its first render, before the clock has
    # moved. Dividing by that elapsed time is a crash.
    session = Session(["like"], clock=FakeClock())
    session.start()

    assert session.tracked_rate == 0.0


# --- starting ----------------------------------------------------------------


def test_start_activates_the_session_and_zeroes_every_tracked_entry():
    session = Session(["like", "well", "to be honest"])
    session.start()

    assert session.is_active is True
    # Every entry is present at 0, so the interface never has to branch on a
    # missing key and every tracked word has a row from the start.
    assert session.counts == {"like": 0, "well": 0, "to be honest": 0}


def test_starting_again_clears_the_previous_session():
    clock = FakeClock()
    session = Session(["like"], clock=clock)

    session.start()
    session.record({"like": 4}, 100)
    clock.advance(60.0)
    session.stop()

    session.start()

    assert session.counts == {"like": 0}
    assert session.total_word_count == 0
    assert session.segments_counted == 0
    assert session.elapsed_seconds == 0.0


# --- recording committed segments --------------------------------------------


def test_a_recorded_segment_folds_into_the_totals():
    tracked = ["like", "well"]
    session = Session(tracked)
    session.start()

    session.record(*count_tracked("well I like it", tracked))

    assert session.counts == {"like": 1, "well": 1}
    assert session.total_word_count == 4
    assert session.segments_counted == 1


def test_the_total_tracked_count_sums_across_entries():
    tracked = ["like", "well"]
    session = Session(tracked)
    session.start()

    session.record(*count_tracked("well well I like it", tracked))

    assert session.total_tracked_count == 3


def test_the_count_never_decrements():
    tracked = ["like", "well"]
    session = Session(tracked)
    session.start()
    seen = []

    for segment in ["well I like it", "no matches here", "like like"]:
        session.record(*count_tracked(segment, tracked))
        seen.append((dict(session.counts), session.total_word_count))

    for (earlier, earlier_words), (later, later_words) in zip(seen, seen[1:]):
        assert later_words >= earlier_words
        assert all(later[word] >= earlier[word] for word in tracked)

    assert session.counts == {"like": 3, "well": 1}
    assert session.total_word_count == 9


def test_no_segment_is_counted_between_the_start_and_the_first_rollover():
    # A segment runs 12 to 45 seconds, so a session that has just started
    # genuinely has nothing to show yet. The interface says it is listening
    # rather than showing a zero, because the silent zeros a denied microphone
    # returns look exactly the same.
    session = Session(["like"])
    session.start()

    assert session.segments_counted == 0

    session.record(*count_tracked("I like it", ["like"]))

    assert session.segments_counted == 1


# --- the rate ----------------------------------------------------------------


def test_the_rate_is_tracked_words_per_minute_of_elapsed_time():
    clock = FakeClock()
    session = Session(["like"], clock=clock)
    session.start()

    session.record({"like": 12}, 300)
    clock.advance(120.0)

    assert session.elapsed_seconds == 120.0
    assert session.tracked_rate == 6.0


def test_the_rate_falls_as_a_quiet_session_runs_on():
    # The same 12 matches across 4 minutes rather than 2. A bare total would
    # make those two sessions indistinguishable, which is the whole reason the
    # rate exists.
    clock = FakeClock()
    session = Session(["like"], clock=clock)
    session.start()

    session.record({"like": 12}, 300)
    clock.advance(240.0)

    assert session.tracked_rate == 3.0


# --- stopping ----------------------------------------------------------------


def test_the_rate_stops_moving_once_the_session_is_stopped():
    clock = FakeClock()
    session = Session(["like"], clock=clock)
    session.start()
    session.record({"like": 12}, 300)
    clock.advance(120.0)

    session.stop()
    frozen = session.tracked_rate
    clock.advance(600.0)

    assert session.is_active is False
    assert session.elapsed_seconds == 120.0
    assert session.tracked_rate == frozen


def test_a_segment_arriving_after_the_stop_changes_nothing():
    # Stopping is confirmed by the person speaking, and the summary they are
    # reading must not move underneath them. Whatever is still in flight from
    # the recognizer is counted before the stop or not at all.
    session = Session(["like"])
    session.start()
    session.record({"like": 2}, 50)
    session.stop()

    session.record({"like": 5}, 100)

    assert session.counts == {"like": 2}
    assert session.total_word_count == 50
    assert session.segments_counted == 1


def test_stopping_twice_is_harmless():
    clock = FakeClock()
    session = Session(["like"], clock=clock)
    session.start()
    clock.advance(90.0)

    session.stop()
    clock.advance(30.0)
    session.stop()

    assert session.elapsed_seconds == 90.0


# --- end to end --------------------------------------------------------------


def test_a_session_fed_a_replayed_run_reports_the_totals():
    # The whole path with no microphone: whole transcripts into the tracker,
    # committed segments into the matcher, matcher output into the session.
    # docs/spike-6-on-device-recognition.md ran for 5 minutes, which is the
    # elapsed time the rate is taken over here.
    tracked = ["like", "counting"]
    clock = FakeClock()
    session = Session(tracked, clock=clock)
    tracker = SegmentTracker()
    session.start()

    for transcript in transcripts.spike6_replay():
        segment = tracker.update(transcript)
        if segment is not None:
            session.record(*count_tracked(segment, tracked))

    session.record(*count_tracked(tracker.flush(), tracked))
    clock.advance(300.0)
    session.stop()

    assert session.segments_counted == 10
    assert session.counts == {"like": 21, "counting": 1}
    assert session.total_word_count == 522
    assert session.total_tracked_count == 22
    assert session.tracked_rate == 4.4
