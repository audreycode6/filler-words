"""Counting tracked words in a transcript that revises itself.

The recognizer hands back the whole transcript on every callback, revises words
it has already emitted, and every 12 to 45 seconds discards it and
starts a new one with no signal that it did. Nothing is counted until the
transcript rolls over, at which point the text last seen is taken as final and
added to the totals -- the count only ever goes up.

    SegmentTracker   hands out finished segments, one per rollover.
    count_tracked    a pure function of one segment's text.
    SessionCounts    the running totals across segments.

docs/design-decisions.md carries the reasoning behind this design.
"""

# A transcript this much shorter than the one before it, or shorter still, has
# rolled over.
ROLLOVER_LENGTH_RATIO = 0.5

# Stripped from the ends of a token, leaving anything inside it alone
#  e.g. "well,", "watermelon's", and "I'm" stay one word each
_TRAILING = ".,!?;:\"'()[]{}—–-…"


def _tokenize(text):
    """Split text into comparable words, lowercased and stripped of punctuation."""
    tokens = []
    for raw in text.split():
        token = raw.lower().strip(_TRAILING)
        if token:
            tokens.append(token)
    return tokens


def count_tracked(text, tracked_words):
    """Count each tracked entry in one segment's text.

    Returns the per-entry counts and the segment's word count. The word count is
    taken here because this is where the text has already been split, and the
    running total lives in SessionCounts.

    Every tracked entry appears in the returned counts, including the ones that
    did not occur -- callers never have to branch on a missing key.
    """
    phrases = {tuple(_tokenize(entry)): entry for entry in tracked_words}
    longest = max((len(phrase) for phrase in phrases), default=0)

    counts = {entry: 0 for entry in tracked_words}
    tokens = _tokenize(text)

    position = 0
    while position < len(tokens):
        # Longest first
        for length in range(min(longest, len(tokens) - position), 0, -1):
            entry = phrases.get(tuple(tokens[position : position + length]))
            if entry is not None:
                counts[entry] += 1
                position += length
                break
        else:
            position += 1

    return counts, len(tokens)


class SegmentTracker:
    """Watches the transcript and hands out segments once they stop changing."""

    def __init__(self):
        self._previous = ""

    def update(self, transcript):
        """Take the latest whole transcript, returning a segment if one ended."""
        previous = self._previous
        self._previous = transcript

        return previous if self._rolled_over(previous, transcript) else None

    def flush(self):
        """Hand over the segment still open, so stopping loses no speech.

        Returns nothing when there is nothing open, so stopping twice cannot
        count the same speech twice.
        """
        open_segment = self._previous
        self._previous = ""

        return open_segment or None

    @staticmethod
    def _rolled_over(previous, current):
        """Tell a rollover apart from the recognizer's close-out rewrite.

        A transcript that still extends the one before it is the same segment
        growing. One that does not may be either of 2 things, and the
        difference is length: the recognizer's close-out pass re-decodes a
        segment at roughly its original length just before discarding it, while
        a rollover replaces it with the first words of new speech. Treating a
        close-out as a rollover would commit the same segment twice.
        """
        if not previous or current.startswith(previous):
            return False

        return len(current) <= ROLLOVER_LENGTH_RATIO * len(previous)


class SessionCounts:
    """The running totals across every segment counted so far."""

    def __init__(self, tracked_words):
        self.counts = {entry: 0 for entry in tracked_words}
        self.total_word_count = 0

    def add(self, counts, word_count):
        """Fold one committed segment's counts into the totals."""
        for entry, count in counts.items():
            self.counts[entry] = self.counts.get(entry, 0) + count
        self.total_word_count += word_count
