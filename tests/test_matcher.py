"""The matcher counts a segment once, after the recognizer has finished with it.

These tests run on saved transcripts and never open a microphone. Each one
builds the tracked-word list it needs rather than importing the shipped list, so
that changing what the app tracks changes no test here.
"""

import config
from fixtures import transcripts
from matcher import SegmentTracker, count_tracked


def commit_all(sequence, tracker=None):
    """Replay whole transcripts through a tracker, returning committed segments."""
    tracker = tracker or SegmentTracker()
    committed = [tracker.update(transcript) for transcript in sequence]
    return [segment for segment in committed if segment is not None]


# --- count_tracked -----------------------------------------------------------


def test_a_word_containing_a_tracked_word_does_not_match_it():
    counts, _ = count_tracked("I also like bros and brothers", ["bro"])

    assert counts["bro"] == 0


def test_case_and_trailing_punctuation_do_not_matter():
    counts, _ = count_tracked("Well, that is Well — well!", ["well"])

    assert counts["well"] == 3


def test_a_multi_word_phrase_counts_once():
    counts, word_count = count_tracked("to be honest I have no idea", ["to be honest"])

    assert counts["to be honest"] == 1
    assert word_count == 7


def test_longest_match_wins_over_a_tracked_sub_word():
    counts, _ = count_tracked(
        "to be honest that is honest work", ["honest", "to be honest"]
    )

    # The phrase consumes its three words, so the "honest" inside it is not
    # available to count again. The later standalone "honest" still is.
    assert counts["to be honest"] == 1
    assert counts["honest"] == 1


def test_every_tracked_word_is_reported_even_at_zero():
    counts, _ = count_tracked("nothing to see", ["bruh", "vibe"])

    assert counts == {"bruh": 0, "vibe": 0}


def test_the_word_count_covers_ordinary_recognizer_output():
    # docs/spike-4-filler-word-preservation.md, the settled run 2 transcript.
    counts, word_count = count_tracked(transcripts.SPIKE4_SETTLED, ["like"])

    assert counts["like"] == 1
    assert word_count == 23


# --- SegmentTracker ----------------------------------------------------------


def test_nothing_counts_before_its_segment_rolls():
    # docs/spike-2-stt-streaming.md: 21 callbacks, no rollover among them.
    assert commit_all(transcripts.SPIKE2_WATERMELON) == []


def test_a_word_carried_by_many_callbacks_counts_once():
    tracker = SegmentTracker()
    commit_all(transcripts.SPIKE2_WATERMELON, tracker)
    segment = tracker.flush()

    counts, _ = count_tracked(segment, ["like"])

    # "like" is carried by fourteen of the twenty-one callbacks and spoken twice.
    assert counts["like"] == 2


def test_a_revised_away_word_is_never_counted():
    tracker = SegmentTracker()
    commit_all(transcripts.SPIKE2_WATERMELON, tracker)
    segment = tracker.flush()

    # "one two" was replaced by "12" and then "123" before the segment ended.
    # docs/spike-2-stt-streaming.md is where that revision was measured.
    counts, _ = count_tracked(segment, ["two", "water"])

    assert counts["two"] == 0
    # "water" was likewise revised into "watermelon".
    assert counts["water"] == 0


def test_a_close_out_is_not_classified_as_a_rollover():
    # docs/spike-6-on-device-recognition.md, +143.21s: the recognizer rewrote
    # the segment from its first word at roughly the same length. Reading that
    # as a rollover would commit the segment twice.
    tracker = SegmentTracker()
    tracker.update(transcripts.SPIKE6_CLOSEOUT_BEFORE)

    assert tracker.update(transcripts.SPIKE6_CLOSEOUT_AFTER) is None


def test_a_close_out_rewriting_the_whole_segment_is_handled():
    # The same pair. What the segment commits is the rewritten text, since the
    # close-out's corrections are what the recognizer settled on.
    tracker = SegmentTracker()
    tracker.update(transcripts.SPIKE6_CLOSEOUT_BEFORE)
    tracker.update(transcripts.SPIKE6_CLOSEOUT_AFTER)
    segment = tracker.update(transcripts.SPIKE6_ROLLOVER_TO)

    assert segment == transcripts.SPIKE6_CLOSEOUT_AFTER
    # "county words" was corrected to "counting words" by the close-out, so a
    # count taken before it and one taken after it are counts of different text.
    counts, _ = count_tracked(segment, ["counting", "county"])
    assert counts["counting"] == 1
    assert counts["county"] == 0


def test_a_length_collapse_is_classified_as_a_rollover():
    # The measured signature: 448 characters replaced by "OK", 0.00s later.
    tracker = SegmentTracker()
    tracker.update(transcripts.SPIKE6_CLOSEOUT_BEFORE)

    assert tracker.update(transcripts.SPIKE6_ROLLOVER_TO) == (
        transcripts.SPIKE6_CLOSEOUT_BEFORE
    )


def test_flush_on_stop_emits_the_open_segment_once():
    tracker = SegmentTracker()
    tracker.update("So I was thinking about the project")

    assert tracker.flush() == "So I was thinking about the project"
    # Stopping twice must not commit the same speech twice.
    assert tracker.flush() is None


def test_flush_after_a_rollover_does_not_re_emit_the_committed_segment():
    tracker = SegmentTracker()
    tracker.update(transcripts.SPIKE6_CLOSEOUT_BEFORE)
    tracker.update(transcripts.SPIKE6_ROLLOVER_TO)

    assert tracker.flush() == transcripts.SPIKE6_ROLLOVER_TO


# --- end to end --------------------------------------------------------------


def test_replaying_the_logged_run_emits_one_segment_per_rollover():
    # docs/spike-6-on-device-recognition.md logged ten of the run's 13
    # rollovers individually, so ten is what a replay built from it can assert.
    tracker = SegmentTracker()
    segments = commit_all(transcripts.spike6_replay(), tracker)
    segments.append(tracker.flush())

    assert len(segments) == 10
    assert [segment.split()[0] for segment in segments] == [
        opening.split()[0] for _, opening in transcripts.SPIKE6_SEGMENT_OPENINGS
    ]


# --- the shipped word list ---------------------------------------------------


def test_the_shipped_word_list_is_well_formed():
    assert config.TRACKED_WORDS

    for word in config.TRACKED_WORDS:
        assert word == word.strip().lower()
        assert word
