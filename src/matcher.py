"""Counting tracked words in a transcript that revises itself.

The recognizer hands back the whole transcript on every callback, revises words
it has already emitted, and every 12 to 45 seconds discards it and starts a new
one. A segment is counted once, at the rollover, from the text last seen before
it.

    SegmentTracker   hands out finished segments, one per rollover.
    count_tracked    a pure function of one segment's text.

The running totals across segments belong to the session, in session.py.
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


def _forms(tracked_words):
    """Pair each habit's name with every form counted toward it.

    Takes either a mapping of name to its other forms, or a plain sequence of
    words, where each word is a habit of one form.
    """
    if hasattr(tracked_words, "items"):
        return {name: (name, *others) for name, others in tracked_words.items()}

    return {entry: (entry,) for entry in tracked_words}


def count_tracked(text, tracked_words):
    """Count each habit in one segment's text.

    Returns the counts keyed by habit name, and the segment's word count from
    the same split. Every form of a habit adds to its name. Every habit appears
    in the counts, including the ones that did not occur.
    """
    habits = _forms(tracked_words)
    phrases = {
        tuple(_tokenize(form)): name
        for name, forms in habits.items()
        for form in forms
    }
    longest = max((len(phrase) for phrase in phrases), default=0)

    counts = {name: 0 for name in habits}
    tokens = _tokenize(text)

    position = 0
    while position < len(tokens):
        # Longest first
        for length in range(min(longest, len(tokens) - position), 0, -1):
            name = phrases.get(tuple(tokens[position : position + length]))
            if name is not None:
                counts[name] += 1
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
        """Hand over the segment still open, and clear it.

        Returns None when nothing is open.
        """
        open_segment = self._previous
        self._previous = ""

        return open_segment or None

    @staticmethod
    def _rolled_over(previous, current):
        """Report whether the transcript rolled over into a new segment.

        A transcript that extends the one before it is the same segment
        growing. One that replaces it at half its length or less is a rollover.
        One that replaces it at roughly its original length is the recognizer's
        close-out rewrite of the same segment.
        """
        if not previous or current.startswith(previous):
            return False

        return len(current) <= ROLLOVER_LENGTH_RATIO * len(previous)

