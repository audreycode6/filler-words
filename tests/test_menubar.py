"""What a session looks like once it has been turned into text.

These tests build no AppKit object and need no window server, so they run
wherever the rest of the suite does. They cover the half of `menubar.py` that
takes a session and returns strings; the half that builds menu items from them
is checked by running `python checks/check_menubar.py`.

Each test builds the tracked-word list it needs rather than importing the
shipped list, so that changing what the app tracks changes no test here.
"""

from menubar import (
    AUTHORIZED,
    DENIED,
    ERROR_HEADER,
    IDLE_HEADER,
    INPUT_STOPPED_HEADER,
    RESTRICTED,
    SUMMARY_HEADER,
    TRACKING_HEADER,
    TRANSCRIBING_HEADER,
    TRANSCRIBING_TITLE,
    authorization_lines,
    elapsed_text,
    has_run,
    input_stopped_guidance,
    menu_header,
    refused_permissions,
    status_title,
    totals_lines,
    word_rows,
)
from session import Session


class FakeClock:
    """A clock a test moves by hand, standing in for time.monotonic."""

    def __init__(self):
        self.seconds = 0.0

    def __call__(self):
        return self.seconds

    def advance(self, seconds):
        self.seconds += seconds


def a_session(tracked, clock=None):
    return Session(tracked, clock=clock or FakeClock())


# --- the menu bar item -------------------------------------------------------


def test_nothing_shows_beside_the_symbol_before_a_session():
    session = a_session(["like"])

    assert status_title(session) == ""


def test_a_started_session_shows_it_is_transcribing():
    # The count is 0 until the first segment commits, and a bare 0 is
    # what a denied microphone's silent audio also produces.
    session = a_session(["like"])
    session.start()

    assert status_title(session) == TRANSCRIBING_TITLE


def test_a_committed_segment_puts_the_count_in_the_title():
    session = a_session(["like"])
    session.start()
    session.record({"like": 3}, 40)

    assert status_title(session) == "3"


def test_a_stopped_session_leaves_the_symbol_alone():
    session = a_session(["like"])
    session.start()
    session.record({"like": 3}, 40)
    session.stop()

    assert status_title(session) == ""


# --- the header --------------------------------------------------------------


def test_an_unstarted_session_names_the_list():
    assert menu_header(a_session(["like"])) == IDLE_HEADER


def test_the_header_moves_from_transcribing_to_tracking_on_the_first_segment():
    # The change of word is what says the count stopped being a starting 0.
    session = a_session(["like"])
    session.start()
    assert menu_header(session) == TRANSCRIBING_HEADER

    session.record({"like": 1}, 12)
    assert menu_header(session) == TRACKING_HEADER


def test_a_stopped_session_is_headed_as_a_summary():
    clock = FakeClock()
    session = a_session(["like"], clock)
    session.start()
    clock.advance(60.0)
    session.stop()

    assert menu_header(session) == SUMMARY_HEADER


def test_a_session_that_committed_nothing_still_reads_as_a_summary():
    # Stopping inside the first segment counts nothing, and the elapsed time is
    # what separates that from a session nobody has started.
    clock = FakeClock()
    session = a_session(["like"], clock)
    session.start()
    clock.advance(8.0)
    session.stop()

    assert has_run(session) is True
    assert menu_header(session) == SUMMARY_HEADER


def test_recognition_having_stopped_outranks_every_other_header():
    # The recognizer can stop on its own while the session still calls itself
    # active, leaving every number below the header standing still.
    session = a_session(["like"])
    session.start()
    session.record({"like": 3}, 40)

    assert menu_header(session, ERROR_HEADER) == ERROR_HEADER

    session.stop()

    assert menu_header(session, ERROR_HEADER) == ERROR_HEADER


def test_the_input_having_stopped_outranks_every_other_header():
    # The microphone can stop sending audio while the session still calls
    # itself active, which reads the same way from the header down.
    session = a_session(["like"])
    session.start()
    session.record({"like": 3}, 40)

    assert menu_header(session, INPUT_STOPPED_HEADER) == INPUT_STOPPED_HEADER


# --- what a stopped input says -----------------------------------------------


def test_the_guidance_names_the_device_the_audio_came_from():
    guidance = input_stopped_guidance("Audrey's Earphones")

    assert "Audrey's Earphones" in guidance
    assert "Start" in guidance


def test_the_guidance_stands_without_a_device_name():
    # The system reports no default input device on some machines, and an
    # empty name would otherwise reach the alert.
    guidance = input_stopped_guidance("")

    assert "the microphone" in guidance
    assert "Start" in guidance


# --- the rows ----------------------------------------------------------------


def test_every_tracked_entry_has_a_row_before_anything_is_said():
    # The row count is bounded by the list, so the menu never reflows, and the
    # rows are the only place the tracked list is visible.
    session = a_session(["like", "well", "to be honest"])

    assert word_rows(session) == [("like", 0), ("well", 0), ("to be honest", 0)]


def test_rows_hold_the_tracked_order_while_a_session_runs():
    session = a_session(["like", "well", "stuff"])
    session.start()
    session.record({"like": 1, "well": 9, "stuff": 4}, 60)

    assert word_rows(session) == [("like", 1), ("well", 9), ("stuff", 4)]


def test_a_stopped_session_sorts_its_rows_by_count():
    session = a_session(["like", "well", "stuff"])
    session.start()
    session.record({"like": 1, "well": 9, "stuff": 4}, 60)
    session.stop()

    assert word_rows(session, ordered_by_count=True) == [
        ("well", 9),
        ("stuff", 4),
        ("like", 1),
    ]


def test_words_sharing_a_count_keep_the_tracked_order():
    # Otherwise 2 sessions with the same totals would list the words differently.
    session = a_session(["like", "well", "stuff", "bruh"])
    session.start()
    session.record({"like": 2, "well": 5, "stuff": 2, "bruh": 0}, 60)

    assert word_rows(session, ordered_by_count=True) == [
        ("well", 5),
        ("like", 2),
        ("stuff", 2),
        ("bruh", 0),
    ]


# --- the totals --------------------------------------------------------------


def test_elapsed_time_reads_as_minutes_and_seconds():
    assert elapsed_text(0.0) == "0:00"
    assert elapsed_text(45.4) == "0:45"
    assert elapsed_text(247.0) == "4:07"
    assert elapsed_text(645.0) == "10:45"


def test_the_totals_name_every_number_they_carry():
    clock = FakeClock()
    session = a_session(["like", "well"], clock)
    session.start()
    session.record({"like": 4, "well": 8}, 604)
    clock.advance(247.0)

    assert totals_lines(session) == (
        "12 of 604 words tracked (2.0%)",
        "4:07 elapsed",
    )


def test_the_totals_hold_still_once_the_session_stops():
    clock = FakeClock()
    session = a_session(["like"], clock)
    session.start()
    session.record({"like": 12}, 604)
    clock.advance(247.0)
    session.stop()

    frozen = totals_lines(session)
    clock.advance(600.0)

    assert totals_lines(session) == frozen


# --- a permission the app cannot listen without ------------------------------


def test_a_refusal_names_only_the_permission_that_was_refused():
    # Each permission is capitalized as the settings pane it names spells it.
    assert authorization_lines(DENIED, DENIED, AUTHORIZED) == (
        "Access denied",
        ("Verbal Habits needs Microphone access.",),
    )
    assert authorization_lines(DENIED, AUTHORIZED, DENIED) == (
        "Access denied",
        ("Verbal Habits needs Speech Recognition access.",),
    )


def test_both_permissions_are_named_when_both_were_refused():
    assert authorization_lines(DENIED, DENIED, DENIED) == (
        "Access denied",
        ("Verbal Habits needs Microphone and Speech Recognition access.",),
    )


def test_a_refusal_from_source_points_at_the_app_that_launched_it():
    # Unbundled, the permission belongs to whichever app ran this code, and
    # that app is what the settings pane lists.
    assert authorization_lines(DENIED, DENIED, AUTHORIZED, bundled=False) == (
        "Access denied",
        ("Turn on Microphone for the app you launched Verbal Habits from.",),
    )


def test_a_refusal_from_source_names_both_permissions_in_one_sentence():
    assert authorization_lines(DENIED, DENIED, DENIED, bundled=False) == (
        "Access denied",
        (
            "Turn on Microphone and Speech Recognition for the app you"
            " launched Verbal Habits from.",
        ),
    )


def test_a_restriction_is_worded_as_something_nobody_can_grant():
    restricted = (
        "Access restricted",
        ("This Mac does not allow microphone access.",),
    )

    assert authorization_lines(RESTRICTED, RESTRICTED, AUTHORIZED) == restricted
    assert (
        authorization_lines(RESTRICTED, RESTRICTED, AUTHORIZED, bundled=False)
        == restricted
    )


def test_a_permission_nobody_has_been_asked_for_is_not_named():
    # The microphone is denied and speech recognition has not been asked for.
    # Denied is the worse of the 2 and is what the app reports, so the message
    # names the microphone alone.
    from audio import UNDETERMINED

    assert refused_permissions(DENIED, DENIED, UNDETERMINED) == ["microphone"]


def test_the_states_named_here_are_the_states_audio_reports():
    # These are mirrored rather than imported, so a rename has to break here
    # rather than at the microphone.
    import audio

    assert (AUTHORIZED, DENIED, RESTRICTED) == (
        audio.AUTHORIZED,
        audio.DENIED,
        audio.RESTRICTED,
    )
