"""Real recognizer output, copied out of the spike write-ups.

Every string here was produced by SFSpeechRecognizer during a spike run and
written down in `docs/`. Each fixture names the write-up it came from.

The recognizer hands back the entire transcript on every callback, not just the
new words, so a sequence here is a list of successive whole transcripts.
"""

# From docs/spike-2-stt-streaming.md, the logged run in full: 21 consecutive
# callbacks, timestamps stripped. 2 revisions are visible in it.
# "watermelon" becomes "watermelon's" one callback later, and "one two" becomes
# "12" and then "123" — a word that was present in the transcript and is gone
# from the next one.
SPIKE2_WATERMELON = [
    "I like",
    "I like to",
    "I like to eat",
    "I like to eat watermelon",
    "I like to eat watermelon's",
    "I like to eat watermelon's",
    "I like to eat watermelon's",
    "I like to eat watermelon's I also",
    "I like to eat watermelon's I also like",
    "I like to eat watermelon's I also like to",
    "I like to eat watermelon's I also like to drink",
    "I like to eat watermelon's I also like to drink water",
    "I like to eat watermelon's I also like to drink watermelon",
    "I like to eat watermelon's I also like to drink watermelon flavored",
    "I like to eat watermelon's I also like to drink watermelon flavored soda",
    "I like to eat watermelon's I also like to drink watermelon flavored soda",
    "I like to eat watermelon's I also like to drink watermelon flavored soda one",
    "I like to eat watermelon's I also like to drink watermelon flavored soda one to",
    "I like to eat watermelon's I also like to drink watermelon flavored soda one two",
    "I like to eat watermelon's I also like to drink watermelon flavored soda 12",
    "I like to eat watermelon's I also like to drink watermelon flavored soda 123",
]

# From docs/spike-6-on-device-recognition.md, the close-out pass logged at
# +143.21s: the recognizer re-decoded the whole segment it was about to
# discard, rewriting from the very first word ("it" became "a"), then replaced
# the transcript with "OK" 0.00s later.
#
# The write-up merge the middle of both sides with a literal "...", which is
# kept here rather than filled in, so the fixture stays something that can be
# checked against the document.
#
# These 2 strings are the pair the rollover check has to tell apart: the
# rewrite preserves the length of the transcript, and the rollover that follows
# collapses it. The write-up measures that collapse at 448 characters to 2.
SPIKE6_CLOSEOUT_BEFORE = (
    "it depends on the transcript staying put once it has been ridden I like "
    "the idea of county words as they settle rather than waiting for the end "
    "it works like a ratchet we're nothing behind the cursor ever moved again "
    "... past the 6 second mark with speech still in progress"
)

SPIKE6_CLOSEOUT_AFTER = (
    "a depends on the transcript staying put once it has been written I like "
    "the idea of counting words as they said or rather than waiting for the "
    "end it works like a ratchet where nothing behind the cursor ever moves "
    "again ... past the 6 second mark with speech still in progress"
)

SPIKE6_ROLLOVER_TO = "OK"

# From the same write-up: the first words of each new segment after a rollover,
# with the time the rollover happened. 13 segments rolled over during the
# 5-minute run and 10 were written down individually, which is why anything
# built from this list counts 10.
SPIKE6_SEGMENT_OPENINGS = [
    (17.10, "I like"),
    (51.36, "So"),
    (69.00, "Where"),
    (106.46, "The"),
    (143.21, "OK"),
    (169.39, "We're"),
    (199.20, "Fire"),
    (211.54, "Staying"),
    (243.45, "My"),
    (287.78, "You"),
]

# From docs/spike-4-filler-word-preservation.md, the settled transcript of run 2.
# Ordinary sentence text, including the two substitutions the spike found: a
# spoken "uh" came back as "a", and a spoken "um" came back as "him".
SPIKE4_SETTLED = (
    "My name is not a Bob sherbet I like love that a short hairdo and I think "
    "I'm going to him talk about."
)


def spike6_replay():
    """A callback sequence covering the 10 segments the write-up logged.

    Assembled rather than replayed: take each logged segment opening,
    grow it the way the recognizer grows a transcript
    — word by word, each callback carrying the whole thing —
    over the 1 full segment body the write-up preserves, and
    let the next opening collapse it.

    The 5th segment carries the close-out rewrite before its rollover, so a
    replay exercises the case where a segment is rewritten end to end and then
    discarded.
    """
    body_words = SPIKE6_CLOSEOUT_BEFORE.split()
    sequence = []

    for index, (_, opening) in enumerate(SPIKE6_SEGMENT_OPENINGS):
        # The opening arrives on its own, collapsing whatever came before it.
        sequence.append(opening)

        # Then the segment grows, three words at a time, each callback carrying
        # the whole transcript so far.
        for end in range(3, len(body_words) + 1, 3):
            sequence.append(opening + " " + " ".join(body_words[:end]))

        grown = opening + " " + " ".join(body_words)
        if sequence[-1] != grown:
            sequence.append(grown)

        # One segment gets the close-out pass: the same length, rewritten from
        # the first word, immediately before the rollover.
        if index == 4:
            sequence.append(opening + " " + SPIKE6_CLOSEOUT_AFTER)

    return sequence
